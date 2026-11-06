import os
import json
from typing import Dict, Optional
from openai import OpenAI
from ..models import TranslationVariants

# Offline high-quality presets for zero-latency testing & dev environments
PRESET_TRANSLATIONS: Dict[str, Dict[str, TranslationVariants]] = {
    "complete purchase - $49.99": {
        "de-de": TranslationVariants(
            standard="Kauf abschließen - 49,99 $",
            compact="Kaufen - 49,99 $",
            ultra_short="Kauf - 49,99 $",
            cultural_notes="German prices use comma decimals and trailing currency sign."
        ),
        "ur-pk": TranslationVariants(
            standard="خریداری مکمل کریں - $49.99",
            compact="خریدیں - $49.99",
            ultra_short="خرید - $49.99",
            cultural_notes="Urdu Nastaliq renders diagonally; preserve LTR price."
        ),
        "ar-sa": TranslationVariants(
            standard="إتمام عملية الشراء - 49.99 $",
            compact="إتمام الشراء - 49.99 $",
            ultra_short="شراء - 49.99 $",
            cultural_notes="Arabic prices often trail the noun in UI action buttons."
        ),
        "ja-jp": TranslationVariants(
            standard="購入を完了する - $49.99",
            compact="購入を完了 - $49.99",
            ultra_short="購入 - $49.99",
            cultural_notes="Japanese drops verb auxiliaries in buttons to preserve space."
        ),
        "fr-fr": TranslationVariants(
            standard="Finaliser la commande - 49,99 $",
            compact="Commander - 49,99 $",
            ultra_short="Payer - 49,99 $",
            cultural_notes="French uses non-breaking space before currency."
        ),
        "es-es": TranslationVariants(
            standard="Completar la compra - 49,99 $",
            compact="Comprar ahora - 49,99 $",
            ultra_short="Comprar - 49,99 $",
            cultural_notes="Spanish commands prefer imperative or infinitive."
        )
    }
}

class LLMTranslator:
    def __init__(self):
        self._client: Optional[OpenAI] = None

    def get_client(self) -> Optional[OpenAI]:
        key = os.getenv("OPENAI_API_KEY")
        if not key:
            try:
                from dotenv import load_dotenv
                load_dotenv()
                key = os.getenv("OPENAI_API_KEY")
            except Exception:
                pass

        if key and (not self._client or self._client.api_key != key):
            self._client = OpenAI(api_key=key)
        return self._client

    def translate_with_variants(
        self,
        source_text: str,
        source_locale: str,
        target_locale: str,
        glossary: Optional[Dict[str, str]] = None
    ) -> TranslationVariants:
        clean_key = source_text.strip().lower()
        clean_locale = target_locale.lower().replace("_", "-")

        # Check offline presets first (instant 0ms)
        if clean_key in PRESET_TRANSLATIONS and clean_locale in PRESET_TRANSLATIONS[clean_key]:
            return PRESET_TRANSLATIONS[clean_key][clean_locale]

        # If OpenAI client is available, call gpt-4o-mini with structured outputs
        client = self.get_client()
        if client:
            try:
                system_prompt = (
                    "You are a layout-aware localization engine. Translate the given UI string into the target locale.\n"
                    "Provide 3 distinct length variants in a single pass:\n"
                    "1. standard: Natural, polite, grammatically complete translation.\n"
                    "2. compact: Shorter phrasing, dropping redundant auxiliary words/articles while strictly preserving core meaning and intent.\n"
                    "3. ultra_short: Minimalist button action verb for tight pixel spaces. CRITICAL: Never invert meaning, drop essential negative words (e.g. 'Cancel' vs 'Confirm'), or omit key nouns.\n"
                    "Preserve all variables, numbers, currency symbols, and technical terms.\n"
                )
                if glossary:
                    system_prompt += f"\nLocked customer glossary terms (DO NOT TRANSLATE DIFFERENTLY):\n{json.dumps(glossary, ensure_ascii=False)}"

                user_prompt = f"Source Text: \"{source_text}\"\nSource Locale: {source_locale}\nTarget Locale: {target_locale}"

                completion = client.beta.chat.completions.parse(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    response_format=TranslationVariants,
                    temperature=0.2,
                )
                return completion.choices[0].message.parsed
            except Exception as e:
                # Log and fallback gracefully
                print(f"[LLMTranslator] OpenAI call failed: {e}. Falling back to heuristic generator.")

        # Fallback synthetic generator for dev / offline mode:
        words = source_text.split()
        if len(words) > 1:
            compact = " ".join(words[:max(1, len(words) - 1)])
            ultra = words[0]
        else:
            compact = source_text
            ultra = source_text

        return TranslationVariants(
            standard=f"[{target_locale}] {source_text}",
            compact=f"[{target_locale}] {compact}",
            ultra_short=f"[{target_locale}] {ultra}",
            cultural_notes="Synthesized fallback variant."
        )

llm_engine = LLMTranslator()
