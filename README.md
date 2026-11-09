# Polyglot Engine — Autonomous Multilingual Layout Scanner & Verified Source Repair Engine

> **Developer CLI & Verification Engine** that audits web applications across multiple locales and viewports, detects container overflows, full-page collisions, and visual BiDi inversion defects in the browser, and produces **closed-loop verified source-code Git patches** directly against your repository.

---

## ⚡ The Core Problem & Solution

Existing localization tools (Lokalise, Phrase, Google Translate) treat strings as abstract text with arbitrary character limits. But character counts do not equal visual layout compatibility:
- A German translation expanding by 35% causes fixed navigation links to truncate or wrap unexpectedly.
- Action buttons in flex rows collide and overlap when labels expand.
- Un-isolated mixed-direction text (e.g. `$49.99` in Arabic/Urdu) suffers from visual punctuation and symbol inversions.

**Polyglot Engine** provides an autonomous, closed-loop engineering QA and repair workflow:
1. **Tree-Walker Whole-DOM Discovery:** Discovers all visible text-bearing UI candidates across the entire DOM tree without relying on hardcoded tag lists.
2. **In-Browser Visual Audit:** Measures live bounding box geometry in headless Chromium to detect container overflows, physical element collisions, and real visual BiDi symbol inversions.
3. **Closed-Loop Verification:** Backtracks across linguistic length variants (`standard` $\rightarrow$ `compact` $\rightarrow$ `ultra_short`), injects calculated dynamic CSS, and verifies reflow in the browser.
4. **Source-Code Git Patching:** Identifies the responsible stylesheet, modifies the CSS rules with property-level precision, validates via `git apply --check`, applies the patch on disk, and verifies that a clean application reload resolves all defects.

```
[Target Web Application] ──► polyglot scan / repair
       │
       ▼
[DOM Discovery & Range Inspection]
  • Whole-DOM traversal across standard elements and custom Web Components
  • Live visual bounding-box collision detection
  • Range-based visual BiDi symbol inversion detection (Zero False Positives)
       │
       ▼
[Multi-Candidate Closed-Loop Repair]
  • Pass 1: Standard translation baseline audit
  • Pass 2 & 3: Multi-length linguistic variant backtracking (compact / ultra-short)
  • Pass 4: Dynamic CSS layout repair (min-width, flex-shrink, margin-right, unicode-bidi)
       │
       ▼
[Source-Code Patcher & Reload Verification]
  • Targets the responsible stylesheet identified by the browser
  • Produces genuine unified Git diff patch (validated via git apply --check)
  • Applies patch on disk, removes in-memory overrides, reloads page, and re-verifies in browser
```

---

## 🚀 CLI Commands

```bash
# 1. Whole-DOM multilingual audit across locales & viewports
polyglot scan https://your-app.com --locales de-DE,ar-SA --viewports desktop,mobile

# 2. Inspect root causes and layout constraints
polyglot diagnose polyglot_audit_report.json

# 3. Closed-loop repair with source-code Git patch generation & reload verification
polyglot repair https://your-app.com --locales de-DE,ar-SA --repo-path /path/to/source --verify
```

---

## 🛠️ Supporting Microservices (Headless Shaping API)

As an optional backend service, Polyglot includes a FastAPI microservice that pairs HarfBuzz OpenType C-shaping (`<1.5ms`) and OpenAI structured outputs for headless advance-width pre-calculation. *(Note: Payment subscriptions and billing tiers are currently on hold to focus 100% on core engineering QA and verified repair).*

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
