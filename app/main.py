import time
from pathlib import Path
from typing import Dict, Any, List
from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from .models import (
    LocalizeRequest,
    LocalizeResponse,
    LocaleResult,
    Metrics,
    OverflowPrevented,
    MeasureRequest,
    MeasureResponse,
    CreateOrderRequest,
    CreateOrderResponse,
    VerifyPaymentRequest,
    VerifyPaymentResponse,
    UIContext
)
from .engines.harfbuzz_meter import harfbuzz_engine
from .engines.bidi_shield import shield_bidi_text
from .engines.css_mapper import get_css_rules
from .engines.llm_translator import llm_engine
from .database import db
from .billing import razorpay_billing, PLANS
from .auth import get_current_org

limiter = Limiter(key_func=get_remote_address, default_limits=["120/minute"])

app = FastAPI(
    title="Polyglot & Layout-Safe Localization API",
    version="1.0.0",
    description="Deterministic layout-aware localization engine with HarfBuzz pixel measurement, BiDi shielding, and Razorpay subscription billing."
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/")
def serve_index():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"message": "Polyglot Engine API is running. Visit /docs for Swagger UI."}

@app.get("/v1/health")
def healthcheck():
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "database": "sqlite_ready",
        "billing_provider": "razorpay",
        "loaded_fonts": list(harfbuzz_engine._font_cache.keys())
    }

@app.post("/v1/measure", response_model=MeasureResponse)
@limiter.limit("60/minute")
def measure_text_endpoint(payload: MeasureRequest, request: Request):
    """
    Direct HarfBuzz measurement endpoint for a single string.
    Returns advance width in pixels in < 2ms.
    """
    width, font_used = harfbuzz_engine.measure_text(
        text=payload.text,
        locale=payload.locale,
        font_size_px=payload.font_size_px,
        font_weight=payload.font_weight
    )
    return MeasureResponse(
        text=payload.text,
        locale=payload.locale,
        measured_width_px=width,
        font_file_used=font_used
    )

@app.post("/v1/localize", response_model=LocalizeResponse)
@limiter.limit("60/minute")
def localize_endpoint(
    req: LocalizeRequest,
    request: Request,
    org_id: str = Depends(get_current_org)
):
    """
    Main layout-safe localization endpoint:
    - Atomic quota reservation
    - Complete cache key lookup (including glossary & padding)
    - 1-pass multi-variant generation
    - HarfBuzz CPU pixel shaping
    - BiDi Unicode isolate wrapping
    - CSS rule mapping
    """
    requested_count = len(req.target_locales)
    
    # Atomic Quota Reservation (Prevents race conditions)
    if not db.check_and_reserve_quota(org_id, count=requested_count):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Monthly translation quota exceeded for this API key. Upgrade plan on Razorpay."
        )

    effective_max_width = req.ui_context.max_width_px - req.ui_context.padding_x_px
    glossary = db.get_glossary(req.glossary_id)
    results = {}

    for target_locale in req.target_locales:
        # Cache key includes all variables: source_locale, target_locale, max_width, font_size, font_weight, padding_x, glossary
        cache_key = db.generate_cache_key(
            source_text=req.source_text,
            source_locale=req.source_locale,
            target_locale=target_locale,
            max_width_px=req.ui_context.max_width_px,
            font_size_px=req.ui_context.font_size_px,
            font_weight=req.ui_context.font_weight,
            padding_x_px=req.ui_context.padding_x_px,
            glossary_id=req.glossary_id
        )
        cached_result = db.get_cache(cache_key)
        if cached_result:
            results[target_locale] = LocaleResult(**cached_result)
            continue

        # 1. Fetch 3 length variants (1-pass LLM call or instant cache/preset)
        variants = llm_engine.translate_with_variants(
            source_text=req.source_text,
            source_locale=req.source_locale,
            target_locale=target_locale,
            glossary=glossary
        )

        # 2. Shape and measure all 3 variants with HarfBuzz
        w_standard, _ = harfbuzz_engine.measure_text(
            variants.standard, target_locale, req.ui_context.font_size_px, req.ui_context.font_weight
        )
        w_compact, _ = harfbuzz_engine.measure_text(
            variants.compact, target_locale, req.ui_context.font_size_px, req.ui_context.font_weight
        )
        w_ultra, _ = harfbuzz_engine.measure_text(
            variants.ultra_short, target_locale, req.ui_context.font_size_px, req.ui_context.font_weight
        )

        # 3. Deterministic selection: pick the best variant that fits
        overflow_prevented = None
        if w_standard <= effective_max_width:
            chosen_text = variants.standard
            chosen_width = w_standard
            variant_used = "standard"
            fits_container = True
            font_scale = 1.0
        elif w_compact <= effective_max_width:
            chosen_text = variants.compact
            chosen_width = w_compact
            variant_used = "compact"
            fits_container = True
            font_scale = 1.0
            overflow_prevented = OverflowPrevented(
                rejected_full_text=variants.standard,
                rejected_width_px=w_standard
            )
        elif w_ultra <= effective_max_width:
            chosen_text = variants.ultra_short
            chosen_width = w_ultra
            variant_used = "ultra_short"
            fits_container = True
            font_scale = 1.0
            overflow_prevented = OverflowPrevented(
                rejected_full_text=variants.standard,
                rejected_width_px=w_standard
            )
        else:
            chosen_text = variants.ultra_short
            chosen_width = w_ultra
            variant_used = "ultra_short"
            fits_container = False
            font_scale = round(effective_max_width / max(w_ultra, 1.0), 2)
            overflow_prevented = OverflowPrevented(
                rejected_full_text=variants.standard,
                rejected_width_px=w_standard
            )

        # 4. Apply BiDi Shield (Unicode isolates)
        ui_safe_text = shield_bidi_text(chosen_text, target_locale)

        # 5. Attach CSS Rules
        css_rules = get_css_rules(target_locale, req.ui_context.font_size_px)

        locale_result = LocaleResult(
            raw_text=chosen_text,
            ui_safe_text=ui_safe_text,
            variant_used=variant_used,
            overflow_prevented=overflow_prevented,
            metrics=Metrics(
                measured_width_px=chosen_width,
                max_width_px=req.ui_context.max_width_px,
                fits_container=fits_container,
                recommended_font_scale=font_scale
            ),
            css_rules=css_rules
        )

        # Cache the result in SQLite
        db.set_cache(cache_key, locale_result.model_dump())
        results[target_locale] = locale_result

    return LocalizeResponse(
        source_text=req.source_text,
        results=results
    )

# --- RAZORPAY BILLING ROUTES ---

@app.get("/v1/billing/plans")
def get_plans():
    return PLANS

@app.post("/v1/billing/create-order", response_model=CreateOrderResponse)
@limiter.limit("20/minute")
def create_order_endpoint(req: CreateOrderRequest, request: Request):
    order = razorpay_billing.create_order(
        plan_id=req.plan_id,
        email=req.email,
        name=req.name
    )
    return CreateOrderResponse(**order)

@app.post("/v1/billing/verify-payment", response_model=VerifyPaymentResponse)
@limiter.limit("10/minute")
def verify_payment_endpoint(req: VerifyPaymentRequest, request: Request):
    result = razorpay_billing.verify_payment_and_issue_key(
        order_id=req.razorpay_order_id,
        payment_id=req.razorpay_payment_id,
        signature=req.razorpay_signature,
        plan_id=req.plan_id,
        email=req.email,
        name=req.name
    )
    return VerifyPaymentResponse(**result)
