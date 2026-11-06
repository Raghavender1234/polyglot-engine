import os
from fastapi import Security, HTTPException, status
from fastapi.security.api_key import APIKeyHeader
from .database import db

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

def get_current_org(api_key: str = Security(API_KEY_HEADER)) -> str:
    """
    Validates the API key from X-API-Key header against SQLite database.
    Checks quota limits and active status.
    """
    # If no key provided, check if in permissive local dev mode
    is_production = os.getenv("ENV", "development").lower() == "production"

    if not api_key:
        if not is_production:
            return "org_default"
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header. Provide a valid Polyglot API key."
        )

    org_info = db.validate_api_key(api_key)
    if not org_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked API Key."
        )

    if org_info["usage_count"] >= org_info["monthly_quota"]:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Monthly translation quota exceeded for this API key. Upgrade plan on Razorpay."
        )

    return org_info["org_id"]
