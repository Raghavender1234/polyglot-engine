from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

class UIContext(BaseModel):
    element_type: str = Field(default="button", description="UI element type (button, nav_tab, badge, header, etc.)")
    max_width_px: float = Field(..., description="Maximum allowed width in pixels")
    font_size_px: float = Field(default=14.0, description="Font size in pixels")
    font_weight: int = Field(default=400, description="Font weight (e.g. 400 for regular, 700 for bold)")
    padding_x_px: float = Field(default=0.0, description="Horizontal padding to subtract from available width")

class LocalizeRequest(BaseModel):
    source_text: str = Field(..., description="Source string to translate and fit")
    source_locale: str = Field(default="en-US", description="Source BCP-47 locale code")
    target_locales: List[str] = Field(..., description="List of target locales (e.g. ['ur-PK', 'de-DE', 'ar-SA', 'ja-JP'])")
    ui_context: UIContext = Field(..., description="UI layout constraints")
    glossary_id: Optional[str] = Field(default=None, description="Optional customer locked glossary ID")
    bypass_presets: bool = Field(default=False, description="When True, bypasses preset dictionaries and forces live AI translation via OpenAI API")

class TranslationVariants(BaseModel):
    standard: str = Field(..., description="Natural, grammatically full translation")
    compact: str = Field(..., description="Shorter synonym or streamlined phrasing")
    ultra_short: str = Field(..., description="Aggressive abbreviation, iconic or concise action verb")
    cultural_notes: Optional[str] = Field(default=None, description="Any cultural warning or layout nuance")

class Metrics(BaseModel):
    measured_width_px: float
    max_width_px: float
    fits_container: bool
    recommended_font_scale: float = 1.0

class OverflowPrevented(BaseModel):
    rejected_full_text: str
    rejected_width_px: float

class CSSRules(BaseModel):
    dir: str
    classes: str
    font_family: str
    line_height: str
    letter_spacing: str
    recommended_min_height_px: Optional[float] = None

class LocaleResult(BaseModel):
    raw_text: str
    ui_safe_text: str
    variant_used: str
    provenance: str = Field(default="OPENAI_API", description="Translation source: OPENAI_API, PRESET, PSEUDO, or FALLBACK")
    overflow_prevented: Optional[OverflowPrevented] = None
    metrics: Metrics
    css_rules: CSSRules

class LocalizeResponse(BaseModel):
    source_text: str
    results: Dict[str, LocaleResult]

class MeasureRequest(BaseModel):
    text: str
    locale: str = "en-US"
    font_size_px: float = 14.0
    font_weight: int = 400

class MeasureResponse(BaseModel):
    text: str
    locale: str
    measured_width_px: float
    font_file_used: str

# Razorpay Billing Models
class CreateOrderRequest(BaseModel):
    plan_id: str = Field(default="starter", description="starter, growth, or enterprise")
    email: str = Field(..., description="Customer email address")
    name: str = Field(default="Customer", description="Customer full name")

class CreateOrderResponse(BaseModel):
    order_id: str
    key_id: str
    amount: int
    currency: str
    plan: str
    plan_name: str
    monthly_quota: int

class VerifyPaymentRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str
    plan_id: str = "starter"
    email: str = "customer@example.com"
    name: str = "Customer"

class VerifyPaymentResponse(BaseModel):
    status: str
    message: str
    api_key: Optional[str] = None
    key_prefix: Optional[str] = None
    key_redacted: bool = False
    org_id: str
    plan: str
    monthly_quota: int

class RegenerateKeyRequest(BaseModel):
    org_id: str
    payment_id: str
    email: str

class RegenerateKeyResponse(BaseModel):
    status: str
    message: str
    api_key: str
    org_id: str
