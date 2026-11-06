import pytest
from app.engines.bidi_shield import shield_bidi_text, LRI, RLI, PDI

def test_bidi_shield_ltr_untouched():
    text = "Complete Purchase - $49.99"
    safe = shield_bidi_text(text, "en-US")
    assert safe == text

def test_bidi_shield_rtl_isolates_prices():
    text = "خریداری مکمل کریں - $49.99"
    safe = shield_bidi_text(text, "ur-PK")

    # Overall string wrapped in RLI and PDI
    assert safe.startswith(RLI)
    assert safe.endswith(PDI)

    # Price island must be wrapped in LRI ... PDI
    assert f"{LRI}$49.99{PDI}" in safe or f"{LRI}49.99{PDI}" in safe

def test_bidi_shield_arabic_version():
    text = "تحديث v2.1 متوفر"
    safe = shield_bidi_text(text, "ar-SA")
    assert safe.startswith(RLI)
    assert safe.endswith(PDI)
    assert f"{LRI}v2.1{PDI}" in safe
