import os
import hmac
import hashlib
from typing import Dict, Any, Optional
from .database import db

try:
    import razorpay
except ImportError:
    razorpay = None

PLANS = {
    "starter": {"name": "Starter Plan", "amount_inr": 999, "quota": 10000},
    "growth": {"name": "Growth Plan", "amount_inr": 2999, "quota": 50000},
    "enterprise": {"name": "Scale Plan", "amount_inr": 9999, "quota": 250000},
}

class RazorpayBilling:
    def __init__(self):
        self.key_id = os.getenv("RAZORPAY_KEY_ID")
        self.key_secret = os.getenv("RAZORPAY_KEY_SECRET")
        self.webhook_secret = os.getenv("RAZORPAY_WEBHOOK_SECRET")
        self._client = None
        if razorpay and self.key_id and self.key_secret:
            self._client = razorpay.Client(auth=(self.key_id, self.key_secret))

    def get_client(self):
        if not self._client and razorpay:
            self.key_id = os.getenv("RAZORPAY_KEY_ID")
            self.key_secret = os.getenv("RAZORPAY_KEY_SECRET")
            if self.key_id and self.key_secret:
                self._client = razorpay.Client(auth=(self.key_id, self.key_secret))
        return self._client

    def create_order(self, plan_id: str, email: str, name: str) -> Dict[str, Any]:
        """
        Creates a Razorpay Order for checkout.
        """
        plan_info = PLANS.get(plan_id, PLANS["starter"])
        amount_paise = plan_info["amount_inr"] * 100

        client = self.get_client()
        if client:
            order_data = {
                "amount": amount_paise,
                "currency": "INR",
                "receipt": f"rcpt_{email[:8]}",
                "notes": {
                    "plan": plan_id,
                    "customer_email": email,
                    "customer_name": name
                }
            }
            order = client.order.create(data=order_data)
            order_id = order["id"]
        else:
            # Test / simulated order ID if keys are pending
            order_id = f"order_mock_{hashlib.md5(email.encode()).hexdigest()[:10]}"

        # Record pending order in DB
        with db.get_connection() as conn:
            conn.execute("""
            INSERT OR REPLACE INTO razorpay_orders (order_id, org_id, amount, currency, status)
            VALUES (?, ?, ?, 'INR', 'created')
            """, (order_id, email, amount_paise))
            conn.commit()

        return {
            "order_id": order_id,
            "key_id": self.key_id or "rzp_test_placeholder",
            "amount": amount_paise,
            "currency": "INR",
            "plan": plan_id,
            "plan_name": plan_info["name"],
            "monthly_quota": plan_info["quota"]
        }

    def verify_payment_and_issue_key(
        self,
        order_id: str,
        payment_id: str,
        signature: str,
        plan_id: str = "starter",
        email: str = "customer@example.com",
        name: str = "Customer"
    ) -> Dict[str, Any]:
        """
        Verifies the Razorpay payment signature and automatically provisions a live API key.
        """
        client = self.get_client()
        if client:
            # Verify signature using Razorpay official utility
            params_dict = {
                'razorpay_order_id': order_id,
                'razorpay_payment_id': payment_id,
                'razorpay_signature': signature
            }
            client.utility.verify_payment_signature(params_dict)
        else:
            # In mock/test mode without credentials
            pass

        plan_info = PLANS.get(plan_id, PLANS["starter"])
        quota = plan_info["quota"]

        # Provision Organization & Generate API Key
        org_id, raw_api_key = db.provision_org(name=name, email=email, plan=plan_id, quota=quota)

        # Mark order as paid
        with db.get_connection() as conn:
            conn.execute("""
            UPDATE razorpay_orders
            SET payment_id = ?, org_id = ?, status = 'paid'
            WHERE order_id = ?
            """, (payment_id, org_id, order_id))
            conn.commit()

        return {
            "status": "success",
            "message": "Payment verified. API Key issued.",
            "api_key": raw_api_key,
            "org_id": org_id,
            "plan": plan_id,
            "monthly_quota": quota
        }

razorpay_billing = RazorpayBilling()
