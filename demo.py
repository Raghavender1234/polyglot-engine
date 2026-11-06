import sys
import json
from fastapi.testclient import TestClient
from app.main import app

if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

client = TestClient(app)

def run_demo():
    print("=" * 70)
    print("   POLYGLOT & LAYOUT-SAFE LOCALIZATION ENGINE DEMO")
    print("=" * 70)

    request_payload = {
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

    print("\n1. REQUEST PAYLOAD (`POST /v1/localize`):")
    print(json.dumps(request_payload, indent=2))

    res = client.post("/v1/localize", json=request_payload)
    print("\n2. RESPONSE STATUS:", res.status_code)
    print("\n3. RESPONSE JSON (with HarfBuzz measurements & BiDi isolates):")
    print(json.dumps(res.json(), indent=2, ensure_ascii=False))

    data = res.json()
    de = data["results"]["de-DE"]
    ur = data["results"]["ur-PK"]
    ar = data["results"]["ar-SA"]

    print("\n" + "=" * 70)
    print("DEMONSTRATION OF VALUE:")
    print(f"- Target Max Width: 145px")
    if de.get("overflow_prevented"):
        print(f"- German Full Text: '{de['overflow_prevented']['rejected_full_text']}' was {de['overflow_prevented']['rejected_width_px']}px (OVERFLOW!)")
        print(f"- German Auto-Swapped: '{de['raw_text']}' is {de['metrics']['measured_width_px']}px (FITS!)")
    
    print(f"- Urdu BiDi-Safe String: {ur['ui_safe_text']!r}")
    print(f"- Urdu CSS Auto-Injected: classes='{ur['css_rules']['classes']}', line-height={ur['css_rules']['line_height']}")
    print(f"- Arabic BiDi-Safe String: {ar['ui_safe_text']!r}")
    print("=" * 70)

if __name__ == "__main__":
    run_demo()
