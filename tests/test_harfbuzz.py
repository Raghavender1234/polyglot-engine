import pytest
import time
from app.engines.harfbuzz_meter import harfbuzz_engine

def test_harfbuzz_latin_measurement():
    t0 = time.perf_counter()
    width, font_used = harfbuzz_engine.measure_text("Complete Purchase - $49.99", "en-US", 14.0)
    elapsed_ms = (time.perf_counter() - t0) * 1000

    assert width > 100.0
    assert font_used == "inter"
    assert elapsed_ms < 15.0 # Extremely fast CPU shaping

def test_harfbuzz_urdu_measurement():
    width, font_used = harfbuzz_engine.measure_text("خریداری مکمل کریں - $49.99", "ur-PK", 14.0)
    assert width > 50.0
    assert font_used == "urdu"

def test_harfbuzz_arabic_measurement():
    width, font_used = harfbuzz_engine.measure_text("إتمام عملية الشراء - 49.99 $", "ar-SA", 14.0)
    assert width > 50.0
    assert font_used == "arabic"

def test_font_size_scaling():
    w_14, _ = harfbuzz_engine.measure_text("Subscribe", "en-US", 14.0)
    w_28, _ = harfbuzz_engine.measure_text("Subscribe", "en-US", 28.0)
    # 28px should be almost exactly double 14px
    assert abs(w_28 - (w_14 * 2)) < 2.0
