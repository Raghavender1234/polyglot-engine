# Polyglot & Layout-Safe Localization API

> **Zero-latency, layout-safe localization engine** powered by **HarfBuzz C-shaping**, **BiDi Unicode isolation**, and **1-pass 3-variant LLM generation**.

---

## 🚀 Key Features

1. **The "Zero-Latency" 1-Pass Architecture**:
   - Generates 3 length variants in a single pass (`standard`, `compact`, `ultra_short`).
   - Uses local CPU OpenType shaping (`uharfbuzz` + `fonttools`) in **< 2ms** to deterministically select the variant that fits the pixel container.
2. **`overflow_prevented` Proof of Value**:
   - Explicitly returns rejected full phrases and their measured overflow width in the API response, proving immediate ROI to developers.
3. **BiDi Shield (`\u2066...\u2069`)**:
   - Automatically wraps LTR islands (currencies, prices, versions, brand names) with Unicode First-Strong Isolates to eliminate broken punctuation in Arabic/Urdu/Hebrew.
4. **CSS Rule Mapping**:
   - Injects required script-specific CSS rules (e.g. `line-height: 1.85` for Urdu Nastaliq ascenders/descenders, `letter-spacing: 0px` for connected Arabic cursives).
5. **Interactive Live Playground**:
   - Built-in web UI with dynamic width and font-size sliders to visualize real-time button overflow and auto-swapping.

---

## 📁 Repository Structure

```text
polyglot-engine/
├── app/
│   ├── main.py                 # FastAPI routes & core localization pipeline
│   ├── models.py               # Pydantic schemas (Request/Response/CSS/Metrics)
│   ├── auth.py                 # API Key authentication & rate limiter
│   ├── billing.py              # Stripe usage reporter & meter events
│   ├── storage.py              # In-memory / cache / glossary concordance store
│   └── engines/
│       ├── harfbuzz_meter.py   # HarfBuzz OpenType C-shaping engine (<2ms)
│       ├── bidi_shield.py      # Unicode isolate injection (\u2066..\u2069)
│       ├── css_mapper.py       # Script-specific CSS properties & line heights
│       └── llm_translator.py   # 1-pass multi-variant translation (gpt-4o-mini + fallback)
├── fonts/                      # Bundled reference OpenType/TrueType fonts
│   ├── Inter-Regular.ttf
│   ├── NotoSansArabic-Regular.ttf
│   ├── NotoNastaliqUrdu-Regular.ttf
│   └── NotoSansJP-Regular.ttf
├── static/
│   └── index.html              # Modern interactive testing playground
├── tests/
│   ├── test_api.py             # API endpoint integration tests
│   ├── test_bidi_shield.py     # BiDi isolation tests
│   └── test_harfbuzz.py        # HarfBuzz pixel measurement & scaling tests
├── demo.py                     # Standalone CLI demonstration script
├── Dockerfile                  # Production container definition
├── requirements.txt
└── README.md
```

---

## ⚡ Quickstart

### 1. Run the Demo CLI
```bash
python demo.py
```

### 2. Run the Test Suite
```bash
python -m pytest -v
```

### 3. Start the Web Server & Interactive Playground
```bash
uvicorn app.main:app --reload --port 8000
```
Open **[http://localhost:8000](http://localhost:8000)** in your browser to interact with the visual button playground!

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

## 🐳 Docker Deployment
```bash
docker build -t polyglot-engine .
docker run -p 8000:8000 polyglot-engine
```
