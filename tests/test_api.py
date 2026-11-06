import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_healthcheck():
    res = client.get("/v1/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert "inter" in data["loaded_fonts"]

def test_measure_endpoint():
    payload = {
        "text": "Sign In",
        "locale": "en-US",
        "font_size_px": 14.0,
        "font_weight": 400
    }
    res = client.post("/v1/measure", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["measured_width_px"] > 20.0
    assert data["font_file_used"] == "inter"

def test_localize_german_compact_swap():
    # Complete Purchase - $49.99 in German:
    # standard: "Kauf abschließen - 49,99 $" (~178px at 14px)
    # compact: "Kaufen - 49,99 $" (~112px at 14px)
    # With max_width_px: 145, it should automatically select compact and return overflow_prevented!
    payload = {
        "source_text": "Complete Purchase - $49.99",
        "source_locale": "en-US",
        "target_locales": ["de-DE"],
        "ui_context": {
            "element_type": "button",
            "max_width_px": 145.0,
            "font_size_px": 14.0,
            "font_weight": 400
        }
    }
    res = client.post("/v1/localize", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "de-DE" in data["results"]
    de_result = data["results"]["de-DE"]

    assert de_result["variant_used"] in ["compact", "ultra_short"]
    assert de_result["overflow_prevented"] is not None
    assert de_result["overflow_prevented"]["rejected_full_text"] == "Kauf abschließen - 49,99 $"
    assert de_result["overflow_prevented"]["rejected_width_px"] > 145.0
    assert de_result["metrics"]["fits_container"] is True

def test_localize_urdu_bidi_and_css():
    payload = {
        "source_text": "Complete Purchase - $49.99",
        "source_locale": "en-US",
        "target_locales": ["ur-PK"],
        "ui_context": {
            "element_type": "button",
            "max_width_px": 145.0,
            "font_size_px": 14.0,
            "font_weight": 400
        }
    }
    res = client.post("/v1/localize", json=payload)
    assert res.status_code == 200
    data = res.json()
    ur_result = data["results"]["ur-PK"]

    assert ur_result["css_rules"]["dir"] == "rtl"
    assert "urdu-mode" in ur_result["css_rules"]["classes"]
    assert ur_result["css_rules"]["line_height"] == "1.85"
    # BiDi check
    assert "\u2067" in ur_result["ui_safe_text"]
    assert ur_result.get("provenance") in ["PRESET", "OPENAI_API", "PSEUDO"]

def test_localize_bypass_presets_provenance():
    payload = {
        "source_text": "Products",
        "source_locale": "en-US",
        "target_locales": ["de-DE"],
        "bypass_presets": True,
        "ui_context": {
            "element_type": "nav_link",
            "max_width_px": 200.0,
            "font_size_px": 14.0,
            "font_weight": 400
        }
    }
    res = client.post("/v1/localize", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "de-DE" in data["results"]
    de = data["results"]["de-DE"]
    # When bypass_presets is True, it must not be PRESET
    assert de.get("provenance") in ["OPENAI_API", "PSEUDO", "FALLBACK"]
    assert de.get("provenance") != "PRESET"
