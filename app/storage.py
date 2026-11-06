import hashlib
import json
from typing import Dict, Optional, Any
from datetime import datetime

class InMemoryStore:
    def __init__(self):
        # Cache: hash -> response dict
        self.cache: Dict[str, Dict[str, Any]] = {}
        # Glossaries: org_id -> glossary_id -> {source_term: locked_translation}
        self.glossaries: Dict[str, Dict[str, str]] = {
            "gls_prod_992": {
                "Purchase": "Kauf",
                "Complete": "Abschließen"
            }
        }
        # Organizations: org_id -> info
        self.organizations: Dict[str, Dict[str, Any]] = {
            "org_default": {
                "name": "Acme Corp",
                "stripe_customer_id": "cus_test_123",
                "tier": "growth",
                "monthly_quota": 50000,
                "usage_count": 0
            }
        }
        # API Keys: key_hash -> org_id
        # Pre-seed a test key: "test_key_polyglot_123"
        test_key = "test_key_polyglot_123"
        hashed = hashlib.sha256(test_key.encode("utf-8")).hexdigest()
        self.api_keys: Dict[str, str] = {
            hashed: "org_default"
        }

    def generate_cache_key(self, source_text: str, locale: str, max_width_px: float, font_size_px: float, font_weight: int) -> str:
        raw = f"{source_text}|{locale.lower()}|{max_width_px:.1f}|{font_size_px:.1f}|{font_weight}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get_cache(self, key: str) -> Optional[Dict[str, Any]]:
        return self.cache.get(key)

    def set_cache(self, key: str, value: Dict[str, Any]):
        self.cache[key] = value

    def get_glossary(self, glossary_id: Optional[str]) -> Optional[Dict[str, str]]:
        if not glossary_id:
            return None
        return self.glossaries.get(glossary_id)

    def set_glossary_term(self, glossary_id: str, source_term: str, locked_term: str):
        if glossary_id not in self.glossaries:
            self.glossaries[glossary_id] = {}
        self.glossaries[glossary_id][source_term] = locked_term

    def validate_api_key(self, raw_key: str) -> Optional[str]:
        hashed = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
        return self.api_keys.get(hashed)

store = InMemoryStore()
