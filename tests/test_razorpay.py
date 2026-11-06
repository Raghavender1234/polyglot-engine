import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import db

client = TestClient(app)

def test_razorpay_order_and_key_issuance_security():
    # 1. Create a Razorpay Order for Growth plan
    order_payload = {
        "plan_id": "growth",
        "email": "alex@polyglot.ai",
        "name": "Alex Developer"
    }
    res = client.post("/v1/billing/create-order", json=order_payload)
    assert res.status_code == 200
    order_data = res.json()
    assert "order_id" in order_data
    assert order_data["amount"] == 299900 # ₹2,999 in paise
    assert order_data["plan"] == "growth"
    assert order_data["monthly_quota"] == 50000

    order_id = order_data["order_id"]

    # 2. Verify Payment (DB resolves plan directly, prevents client tampering)
    verify_payload = {
        "razorpay_order_id": order_id,
        "razorpay_payment_id": "pay_test_9988776655",
        "razorpay_signature": "sig_test_dummy",
        "email": "alex@polyglot.ai",
        "name": "Alex Developer"
    }
    verify_res = client.post("/v1/billing/verify-payment", json=verify_payload)
    assert verify_res.status_code == 200
    issued_data = verify_res.json()

    assert issued_data["status"] == "success"
    assert issued_data["plan"] == "growth"
    assert issued_data["monthly_quota"] == 50000
    assert issued_data["api_key"].startswith("pk_live_")
    new_api_key = issued_data["api_key"]

    # 3. Replay Protection: verify that calling verify-payment again with the same order fails
    replay_res = client.post("/v1/billing/verify-payment", json=verify_payload)
    assert replay_res.status_code == 400
    assert "already processed" in replay_res.json()["detail"].lower() or "not found" in replay_res.json()["detail"].lower()

    # 4. Authorized request with new key
    loc_res = client.post(
        "/v1/localize",
        json={
            "source_text": "Complete Purchase - $49.99",
            "source_locale": "en-US",
            "target_locales": ["de-DE"],
            "ui_context": {
                "element_type": "button",
                "max_width_px": 145.0,
                "font_size_px": 14.0
            }
        },
        headers={"X-API-Key": new_api_key}
    )
    assert loc_res.status_code == 200
    assert "de-DE" in loc_res.json()["results"]
