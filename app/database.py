import sqlite3
import hashlib
import json
import secrets
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from datetime import datetime

DB_PATH = Path(__file__).resolve().parent.parent / "polyglot.db"

class Database:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = str(db_path)
        self.init_db()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Organizations
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS organizations (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT,
                plan TEXT DEFAULT 'free',
                monthly_quota INTEGER DEFAULT 1000,
                usage_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)

            # API Keys
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS api_keys (
                id TEXT PRIMARY KEY,
                org_id TEXT NOT NULL,
                key_prefix TEXT NOT NULL,
                key_hash TEXT NOT NULL UNIQUE,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (org_id) REFERENCES organizations(id)
            )
            """)

            # Razorpay Orders
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS razorpay_orders (
                order_id TEXT PRIMARY KEY,
                payment_id TEXT,
                org_id TEXT,
                amount INTEGER,
                currency TEXT,
                status TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)

            # Cache
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS translation_cache (
                hash_key TEXT PRIMARY KEY,
                response_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)

            # Glossaries
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS glossaries (
                glossary_id TEXT,
                source_term TEXT,
                locked_translation TEXT,
                PRIMARY KEY (glossary_id, source_term)
            )
            """)

            # Ensure default org & default dev key exists
            cursor.execute("SELECT id FROM organizations WHERE id = 'org_default'")
            if not cursor.fetchone():
                cursor.execute("""
                INSERT INTO organizations (id, name, email, plan, monthly_quota)
                VALUES ('org_default', 'Default Org', 'dev@polyglot.local', 'developer', 50000)
                """)
                test_key = "test_key_polyglot_123"
                test_hash = hashlib.sha256(test_key.encode("utf-8")).hexdigest()
                cursor.execute("""
                INSERT INTO api_keys (id, org_id, key_prefix, key_hash)
                VALUES ('key_default', 'org_default', 'test_key', ?)
                """, (test_hash,))

            conn.commit()

    # Cache Operations
    def generate_cache_key(self, source_text: str, locale: str, max_width_px: float, font_size_px: float, font_weight: int) -> str:
        raw = f"{source_text}|{locale.lower()}|{max_width_px:.1f}|{font_size_px:.1f}|{font_weight}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get_cache(self, key: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            row = conn.execute("SELECT response_json FROM translation_cache WHERE hash_key = ?", (key,)).fetchone()
            if row:
                return json.loads(row["response_json"])
        return None

    def set_cache(self, key: str, value: Dict[str, Any]):
        with self.get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO translation_cache (hash_key, response_json) VALUES (?, ?)",
                (key, json.dumps(value, ensure_ascii=False))
            )
            conn.commit()

    # Auth & API Keys
    def validate_api_key(self, raw_key: str) -> Optional[Dict[str, Any]]:
        hashed = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
        with self.get_connection() as conn:
            row = conn.execute("""
            SELECT a.org_id, o.plan, o.monthly_quota, o.usage_count
            FROM api_keys a
            JOIN organizations o ON a.org_id = o.id
            WHERE a.key_hash = ? AND a.is_active = 1
            """, (hashed,)).fetchone()
            if row:
                return dict(row)
        return None

    def create_api_key(self, org_id: str) -> Tuple[str, str]:
        """
        Generates a new secure live key (pk_live_...)
        Returns (raw_plaintext_key, key_id).
        Only the SHA-256 hash is stored in the database.
        """
        raw_token = secrets.token_hex(20)
        raw_key = f"pk_live_{raw_token}"
        key_id = f"key_{secrets.token_hex(6)}"
        key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
        key_prefix = raw_key[:12]

        with self.get_connection() as conn:
            conn.execute("""
            INSERT INTO api_keys (id, org_id, key_prefix, key_hash)
            VALUES (?, ?, ?, ?)
            """, (key_id, org_id, key_prefix, key_hash))
            conn.commit()

        return raw_key, key_id

    # Provision Organization
    def provision_org(self, name: str, email: str, plan: str, quota: int) -> Tuple[str, str]:
        """
        Provisions a new organization and generates its initial live API key.
        Returns (org_id, raw_api_key).
        """
        org_id = f"org_{secrets.token_hex(6)}"
        with self.get_connection() as conn:
            conn.execute("""
            INSERT INTO organizations (id, name, email, plan, monthly_quota)
            VALUES (?, ?, ?, ?, ?)
            """, (org_id, name, email, plan, quota))
            conn.commit()

        raw_key, _ = self.create_api_key(org_id)
        return org_id, raw_key

    def record_usage(self, org_id: str, count: int = 1) -> int:
        with self.get_connection() as conn:
            conn.execute("""
            UPDATE organizations SET usage_count = usage_count + ? WHERE id = ?
            """, (count, org_id))
            conn.commit()
            row = conn.execute("SELECT usage_count FROM organizations WHERE id = ?", (org_id,)).fetchone()
            return row["usage_count"] if row else count

    def get_glossary(self, glossary_id: Optional[str]) -> Optional[Dict[str, str]]:
        if not glossary_id:
            return None
        with self.get_connection() as conn:
            rows = conn.execute("SELECT source_term, locked_translation FROM glossaries WHERE glossary_id = ?", (glossary_id,)).fetchall()
            if rows:
                return {r["source_term"]: r["locked_translation"] for r in rows}
        return None

db = Database()
