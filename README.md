# Polyglot Engine — Layout-Safe Localization & UI Protection

> **Developer-first localization engine** that pairs **HarfBuzz OpenType C-shaping**, **BiDi Unicode isolation**, and **multi-variant LLM translation** with **Razorpay subscriptions** and **CI/CD layout testing**.

---

## ⚡ The Real Value Proposition

Existing localization platforms (Lokalise, Phrase, Google Translate) treat strings as abstract text with arbitrary character limits. But character counts do not equal pixel widths:
- 15 characters of `"iiiiiiiiiiiiiii"` is **~48px**.
- 15 characters of `"WWWWWWWWWWWWWWW"` is **~195px**.

Polyglot Engine physically shapes text against real OpenType TrueType binaries (`.ttf`) in **< 1.5ms**, detects button/container overflows before release, and automatically swaps in meaning-preserving compact variants.

```
[Client App / CI/CD Pipeline]
       │
       ▼  POST /v1/localize (Text + Max Width PX + Font Size + Locale)
[FastAPI Gateway (Python 3.12)]
       │
       ├──► 1. Check SQLite Cache (Full parameter hash) ──► [HIT: Return in < 4ms]
       │
       ▼  (Cache Miss)
[OpenAI API (gpt-4o-mini / Strict Structured Outputs)]
  • Generates 3 semantic length variants in a single pass: [Standard, Compact, Ultra-Short]
  • Preserves variables, currency formats, and glossary terms
       │
       ▼
[Deterministic C-Shaping Engine]
  ├──► Step A: HarfBuzz shapes all 3 variants against real .ttf font files
  │            (Noto Nastaliq Urdu, Noto Sans Arabic, Inter, Noto Sans JP)
  │            Selects the most natural variant that fits <= max_width_px
  ├──► Step B: BiDi Shield wraps numbers, prices, and LTR islands in Unicode isolates (\u2066...\u2069)
  └──► Step C: CSS Mapper injects script rules (e.g. line-height: 1.85 for Urdu Nastaliq descenders)
       │
       ▼
[Save to SQLite DB + Atomically Track Monthly Quota] ──► Return JSON Response
```

---

## 🚀 Key Capabilities

1. **Deterministic HarfBuzz Shaping**: Real OpenType advance-width calculation on CPU in **~1.1ms**.
2. **`overflow_prevented` Proof-of-Value**: The API explicitly returns the rejected full string and its pixel width in the payload so developers immediately see what was saved.
3. **BiDi Unicode Isolates (`\u2066...\u2069`)**: Protects mixed LTR/RTL text (e.g. prices like `$49.99` in Arabic/Urdu) from punctuation flipping bugs.
4. **Persistent SQLite Database (`polyglot.db`)**: Stores organizations, hashed API keys (`pk_live_...`), quotas, orders, and cache across restarts.
5. **Razorpay Subscriptions**: Integrated payment order creation and signature verification (`app/billing.py`).
6. **Rate Limiting**: Built-in `slowapi` rate limiter on all endpoints to prevent API abuse.
7. **CI/CD Automated Localization**: Comes with [`scripts/ci_check.py`](scripts/ci_check.py) and [`.github/workflows/polyglot-ci.yml`](.github/workflows/polyglot-ci.yml) to scan `locales/en.json` and generate localized files automatically.

---

## 📁 Repository Structure

```text
polyglot-engine/
├── polyglot/                   # Modular Autonomous Layout & Closed-Loop Repair Package
│   ├── __init__.py             # Version 1.3.0
│   ├── cli.py                  # Developer CLI (scan, diagnose, repair)
│   ├── scanner.py              # DOM element discovery & tree-walker text extractor
│   ├── detector.py             # Whole-page collision & container overflow detector
│   ├── diagnosis.py            # Computed layout constraint & root-cause analyzer
│   ├── patcher.py              # Dynamic geometry CSS generator & Git diff patcher
│   ├── repair.py               # Closed-loop backtracking repair orchestrator
│   └── reporting.py            # Evidence-based, truthful HTML/JSON reporting
├── app/
│   ├── main.py                 # FastAPI routes, rate limiter, and core pipeline
│   ├── models.py               # Pydantic schemas (Request/Response/Razorpay/Metrics)
│   ├── database.py             # SQLite manager: orgs, hashed keys, orders, cache
│   ├── billing.py              # Razorpay checkout & signature verification
│   ├── auth.py                 # API Key authentication & quota enforcement
│   └── engines/
│       ├── harfbuzz_meter.py   # HarfBuzz OpenType C-shaping engine (<1.5ms)
│       ├── bidi_shield.py      # Unicode isolate injection (\u2066..\u2069)
│       ├── css_mapper.py       # Script-specific CSS properties & line heights
│       └── llm_translator.py   # 1-pass multi-variant translation (gpt-4o-mini + fallback)
├── fonts/                      # Bundled reference OpenType TrueType fonts
├── static/                     # Dark-mode visual playground & audit proof showcase
├── scripts/                    # Headless inspection & CI scripts
├── tests/
│   ├── test_polyglot_modules.py# Patcher, detector, diagnosis & reporting tests
│   ├── test_api.py             # API endpoint integration tests
│   ├── test_bidi_shield.py     # BiDi isolation tests
│   ├── test_harfbuzz.py        # HarfBuzz pixel measurement & scaling tests
│   └── test_razorpay.py        # Razorpay order & key issuance tests
├── pyproject.toml              # Build config & console script entrypoint
├── requirements.txt
└── polyglot.db
```

---

## 🛠️ Polyglot CLI — Automated Layout Scanner & Repair Engine

Polyglot includes a clean developer CLI to scan any live URL or web app, diagnose root causes, and execute closed-loop layout repairs in an isolated browser.

### 1. Full-Page Multilingual Layout Scan
Scan any webpage across multiple target locales and viewports. Inspects the entire DOM, detects text overflows, and tests element bounding boxes against all visible page elements for collisions:
```bash
polyglot scan https://play.grafana.org/alerting/list --locales de-DE,ar-SA --viewports desktop,mobile --output audit.html --json audit.json
```

### 2. Root-Cause Layout Diagnosis
Inspect why text broke or collided (e.g. `FLEX_CONTAINER_NO_WRAP`, `CSS_RIGID_WIDTH_CONSTRAINT`, `BIDI_DIRECTIONAL_ISOLATION`, or linguistic text expansion) and get actionable CSS remedies:
```bash
polyglot diagnose audit.json
```

### 3. Closed-Loop Multi-Candidate Repair & Verification
Backtracks across candidate translation lengths (`standard` → `compact` → `ultra_short`), injects dynamically calculated non-hardcoded CSS overrides, re-evaluates in Playwright, and produces verified proof:
```bash
polyglot repair http://localhost:8000/static/showcase.html --locales de-DE --repo-path . --output repair.html
```

---

## ⚡ Quickstart

### 1. Run the Test Suite
```bash
python -m pytest -v
```

### 2. Start the Server & Live Playground
```bash
uvicorn app.main:app --reload --port 8000
```
Open **[http://localhost:8000](http://localhost:8000)** in your browser for the interactive testing playground.

### 3. Run the CI/CD Localization Script on a JSON file
```bash
python scripts/ci_check.py --input locales/en.json --targets de-DE,ur-PK,ar-SA,ja-JP
```

---

## 📡 API Contract

### Request: `POST /v1/localize`
```json
{
  "source_text": "Complete Purchase - $49.99",
  "source_locale": "en-US",
  "target_locales": ["ur-PK", "ar-SA", "de-DE", "ja-JP"],
  "ui_context": {
    "element_type": "button",
    "max_width_px": 145,
    "font_size_px": 14
  },
  "glossary_id": "gls_prod_992"
}
```

### Response: `200 OK`
```json
{
  "source_text": "Complete Purchase - $49.99",
  "results": {
    "de-DE": {
      "raw_text": "Kaufen - 49,99 $",
      "ui_safe_text": "Kaufen - 49,99 $",
      "variant_used": "compact",
      "overflow_prevented": {
        "rejected_full_text": "Kauf abschließen - 49,99 $",
        "rejected_width_px": 180.67
      },
      "metrics": {
        "measured_width_px": 112.66,
        "max_width_px": 145.0,
        "fits_container": true,
        "recommended_font_scale": 1.0
      },
      "css_rules": {
        "dir": "ltr",
        "classes": "ltr-mode",
        "font_family": "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
        "line_height": "1.25",
        "letter_spacing": "normal"
      }
    }
  }
}
```

---

## 🐳 Render Deployment
1. Connect your GitHub repository to [render.com](https://render.com).
2. Render detects `render.yaml` and `Dockerfile`.
3. Provide environment variables:
   - `OPENAI_API_KEY`
   - `RAZORPAY_KEY_ID`
   - `RAZORPAY_KEY_SECRET`
   - `ENV=production`
