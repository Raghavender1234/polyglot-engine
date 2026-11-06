import os
import hmac
import hashlib
from typing import Dict, Any, Optional
from fastapi import HTTPException
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
        self.is_production = os.getenv("ENV", "development").lower() == "production"
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
        if plan_id not in PLANS:
            plan_id = "starter"

        plan_info = PLANS[plan_id]
        amount_paise = plan_info["amount_inr"] * 100

        client = self.get_client()
        if client:
            order_data = {
                "amount": amount_paise,
                "currency": "INR",
                "receipt": f"rcpt_{email[:8]}_{int(hashlib.md5(email.encode()).hexdigest()[:6], 16)}",
                "notes": {
                    "plan_id": plan_id,
                    "customer_email": email,
                    "customer_name": name
                }
            }
            order = client.order.create(data=order_data)
            order_id = order["id"]
        else:
            if self.is_production:
                raise HTTPException(
                    status_code=500,
                    detail="Payment gateway misconfigured: RAZORPAY_KEY_ID/SECRET missing in production."
                )
            order_id = f"order_mock_{hashlib.md5((email + plan_id).encode()).hexdigest()[:12]}"

        # Store plan_id and amount in database to prevent client plan manipulation
        with db.get_connection() as conn:
            conn.execute("""
            INSERT OR REPLACE INTO razorpay_orders (order_id, org_id, plan_id, amount, currency, status)
            VALUES (?, ?, ?, ?, 'INR', 'created')
            """, (order_id, email, plan_id, amount_paise))
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
        email: str = "customer@example.com",
        name: str = "Customer"
    ) -> Dict[str, Any]:
        """
        Secure verification:
        1. Atomic status transition: UPDATE status = 'paid' WHERE order_id = ? AND status = 'created'.
           If 0 rows updated, request fails immediately (prevents concurrent replay races).
        2. Plan is read directly from DB order record, NEVER trusted from client input.
        3. HMAC-SHA256 signature verification via Razorpay utility.
        """
        # Step 1: Signature verification
        client = self.get_client()
        if client:
            try:
                params_dict = {
                    'razorpay_order_id': order_id,
                    'razorpay_payment_id': payment_id,
                    'razorpay_signature': signature
                }
                client.utility.verify_payment_signature(params_dict)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid payment signature: {str(e)}")
        else:
            if self.is_production:
                raise HTTPException(
                    status_code=500,
                    detail="Cannot verify payment: RAZORPAY_KEY_SECRET missing in production."
                )

        # Step 2: Atomic Transition to 'paid' (Prevents replay race condition)
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            UPDATE razorpay_orders
            SET payment_id = ?, status = 'paid'
            WHERE order_id = ? AND status = 'created'
            """, (payment_id, order_id))
            conn.commit()

            if cursor.rowcount == 0:
                raise HTTPException(
                    status_code=400,
                    detail="Order not found or payment already processed."
                )

            # Step 3: Fetch verified plan_id directly from the DB record
            row = conn.execute(
                "SELECT plan_id, org_id FROM razorpay_orders WHERE order_id = ?",
                (order_id,)
            ).fetchone()

        verified_plan = row["plan_id"]
        customer_email = row["org_id"] or email
        plan_info = PLANS.get(verified_plan, PLANS["starter"])
        quota = plan_info["quota"]

        # Step 4: Provision Org & Generate Secure API Key
        org_id, raw_api_key = db.provision_org(name=name, email=customer_email, plan=verified_plan, quota=quota)

        return {
            "status": "success",
            "message": "Payment verified. API Key issued.",
            "api_key": raw_api_key,
            "org_id": org_id,
            "plan": verified_plan,
            "monthly_quota": quota
        }

razorpay_billing = RazorpayBilling()
