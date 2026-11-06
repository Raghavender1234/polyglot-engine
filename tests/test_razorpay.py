import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import db

client = TestClient(app)

def test_razorpay_order_and_key_issuance():
    # 1. Create a Razorpay Order
    order_payload = {
        "plan_id": "starter",
        "email": "testuser@polyglot.ai",
        "name": "Alex Developer"
    }
    res = client.post("/v1/billing/create-order", json=order_payload)
    assert res.status_code == 200
    order_data = res.json()
    assert "order_id" in order_data
    assert order_data["amount"] == 99900 # ₹999 in paise
    assert order_data["currency"] == "INR"
    assert order_data["monthly_quota"] == 10000

    order_id = order_data["order_id"]

    # 2. Verify Payment & Automatically Issue Live Key
    verify_payload = {
        "razorpay_order_id": order_id,
        "razorpay_payment_id": "pay_test_123456789",
        "razorpay_signature": "sig_test_dummy",
        "plan_id": "starter",
        "email": "testuser@polyglot.ai",
        "name": "Alex Developer"
    }
    verify_res = client.post("/v1/billing/verify-payment", json=verify_payload)
    assert verify_res.status_code == 200
    issued_data = verify_res.json()

    assert issued_data["status"] == "success"
    assert issued_data["api_key"].startswith("pk_live_")
    new_api_key = issued_data["api_key"]

    # 3. Test Making an Authorized API Request with the new key
    localize_payload = {
        "source_text": "Complete Purchase - $49.99",
        "source_locale": "en-US",
        "target_locales": ["de-DE"],
        "ui_context": {
            "element_type": "button",
            "max_width_px": 145.0,
            "font_size_px": 14.0
        }
    }
    loc_res = client.post(
        "/v1/localize",
        json=localize_payload,
        headers={"X-API-Key": new_api_key}
    )
    assert loc_res.status_code == 200
    loc_data = loc_res.json()
    assert "de-DE" in loc_data["results"]
