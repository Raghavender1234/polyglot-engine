import os
import json
import re
from typing import Dict, Optional, Tuple, Any
from ..models import TranslationVariants

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# Offline high-quality presets for zero-latency testing, demo environments, and common UI vocabulary
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
            standard="إتمام عملية الشراء: $49.99",
            compact="إتمام الشراء: $49.99",
            ultra_short="شراء: $49.99",
            cultural_notes="Arabic mixed-direction price requires BiDi isolation to prevent $ symbol inversion."
        ),
        "ja-jp": TranslationVariants(
            standard="購入を完了する - $49.99",
            compact="購入を完了 - $49.99",
            ultra_short="購入 - $49.99",
            cultural_notes="Japanese drops verb auxiliaries in buttons to preserve space."
        )
    },
    "subscribe to pro (annual)": {
        "de-de": TranslationVariants(
            standard="Pro-Abonnement abschließen (jährlich)",
            compact="Pro abonnieren (jährlich)",
            ultra_short="Pro Jahresabo",
            cultural_notes="German compound nouns are concise in ultra_short."
        ),
        "ur-pk": TranslationVariants(
            standard="پرو کی سالانہ رکنیت حاصل کریں",
            compact="پرو سبسکرائب کریں (سالانہ)",
            ultra_short="پرو سالانہ",
            cultural_notes="Urdu subscription action."
        ),
        "ar-sa": TranslationVariants(
            standard="الاشتراك في الخطة الاحترافية (سنوياً)",
            compact="الاشتراك في برو (سنوي)",
            ultra_short="اشتراك سنوي",
            cultural_notes="Arabic action verb for subscriptions."
        ),
        "ja-jp": TranslationVariants(
            standard="Proプランに登録する（年額）",
            compact="Proに登録（年額）",
            ultra_short="Pro年額登録",
            cultural_notes="Japanese nominalized action."
        )
    },
    "sign in with google account": {
        "de-de": TranslationVariants(
            standard="Mit Google-Konto anmelden",
            compact="Mit Google anmelden",
            ultra_short="Google-Login",
            cultural_notes="German tech users recognize Google-Login."
        ),
        "ur-pk": TranslationVariants(
            standard="گوگل اکاؤنٹ کے ذریعے سائن ان کریں",
            compact="گوگل سے سائن ان",
            ultra_short="گوگل سائن ان",
            cultural_notes="Urdu third-party OAuth CTA."
        ),
        "ar-sa": TranslationVariants(
            standard="تسجيل الدخول باستخدام حساب جوجل",
            compact="الدخول عبر جوجل",
            ultra_short="دخول جوجل",
            cultural_notes="Arabic concise OAuth."
        ),
        "ja-jp": TranslationVariants(
            standard="Googleアカウントでログインする",
            compact="Googleでログイン",
            ultra_short="Googleログイン",
            cultural_notes="Japanese standard OAuth button."
        )
    },
    "products": {
        "de-de": TranslationVariants(standard="Produkte", compact="Produkte", ultra_short="Prod.", cultural_notes="German UI navigation."),
        "ur-pk": TranslationVariants(standard="مصنوعات", compact="مصنوعات", ultra_short="پروڈکٹس", cultural_notes="Urdu menu item."),
        "ar-sa": TranslationVariants(standard="المنتجات", compact="منتجات", ultra_short="منتجات", cultural_notes="Arabic navigation."),
        "ja-jp": TranslationVariants(standard="製品一覧", compact="製品", ultra_short="製品", cultural_notes="Japanese navigation.")
    },
    "pricing": {
        "de-de": TranslationVariants(standard="Preise und Tarife", compact="Preise", ultra_short="Preise", cultural_notes="German pricing."),
        "ur-pk": TranslationVariants(standard="قیمتیں اور پلانز", compact="قیمتیں", ultra_short="قیمت", cultural_notes="Urdu pricing."),
        "ar-sa": TranslationVariants(standard="الأسعار والباقات", compact="الأسعار", ultra_short="الأسعار", cultural_notes="Arabic pricing."),
        "ja-jp": TranslationVariants(standard="料金プラン", compact="料金", ultra_short="料金", cultural_notes="Japanese pricing.")
    },
    "get started": {
        "de-de": TranslationVariants(standard="Jetzt kostenlos starten", compact="Jetzt starten", ultra_short="Starten", cultural_notes="German CTA."),
        "ur-pk": TranslationVariants(standard="ابھی مفت شروع کریں", compact="شروع کریں", ultra_short="شروع", cultural_notes="Urdu CTA."),
        "ar-sa": TranslationVariants(standard="ابدأ مجاناً الآن", compact="ابدأ الآن", ultra_short="ابدأ", cultural_notes="Arabic CTA."),
        "ja-jp": TranslationVariants(standard="無料で今すぐ始める", compact="今すぐ始める", ultra_short="始める", cultural_notes="Japanese CTA.")
    },
    "talk to sales": {
        "de-de": TranslationVariants(standard="Vertriebsteam kontaktieren", compact="Vertrieb kontaktieren", ultra_short="Kontakt", cultural_notes="German sales."),
        "ur-pk": TranslationVariants(standard="سیلز ٹیم سے رابطہ کریں", compact="سیلز سے رابطہ", ultra_short="رابطہ", cultural_notes="Urdu sales."),
        "ar-sa": TranslationVariants(standard="تحدث مع فريق المبيعات", compact="تواصل مع المبيعات", ultra_short="المبيعات", cultural_notes="Arabic sales."),
        "ja-jp": TranslationVariants(standard="営業チームにお問い合わせ", compact="営業へ相談", ultra_short="問い合わせ", cultural_notes="Japanese sales.")
    },
    "case study": {
        "de-de": TranslationVariants(standard="Ausführliche Fallstudie", compact="Fallstudie", ultra_short="Studie", cultural_notes="German case study."),
        "ur-pk": TranslationVariants(standard="مکمل کیس اسٹڈی", compact="کیس اسٹڈی", ultra_short="مطالعہ", cultural_notes="Urdu case study."),
        "ar-sa": TranslationVariants(standard="دراسة حالة مفصلة", compact="دراسة حالة", ultra_short="دراسة", cultural_notes="Arabic case study."),
        "ja-jp": TranslationVariants(standard="導入事例の詳細", compact="導入事例", ultra_short="事例", cultural_notes="Japanese case study.")
    },
    "finding a time took a week of emails.": {
        "de-de": TranslationVariants(
            standard="Einen passenden Termin zu finden, dauerte eine Woche voller E-Mails.",
            compact="Terminfindung dauerte eine Woche per E-Mail.",
            ultra_short="Terminfindung dauerte 1 Woche.",
            cultural_notes="German maintains full semantic clause."
        ),
        "ur-pk": TranslationVariants(
            standard="مناسب وقت طے کرنے میں ای میلز کے تبادلے کا پورا ایک ہفتہ لگ جاتا تھا۔",
            compact="وقت طے کرنے میں ہفتہ بھر کی ای میلز لگیں۔",
            ultra_short="وقت طے کرنے میں 1 ہفتہ لگا۔",
            cultural_notes="Urdu preserves subject and timeline."
        ),
        "ar-sa": TranslationVariants(
            standard="كان إيجاد موعد مناسب يستغرق أسبوعاً كاملاً من رسائل البريد الإلكتروني.",
            compact="تنسيق الموعد تطلب أسبوعاً من الرسائل.",
            ultra_short="حجز الموعد استغرق أسبوعاً.",
            cultural_notes="Arabic keeps full verbal sentence."
        ),
        "ja-jp": TranslationVariants(
            standard="日程を調整するだけで、1週間ものメールの往復が必要でした。",
            compact="日程調整に1週間のメールを消費。",
            ultra_short="日程調整に1週間を要した。",
            cultural_notes="Japanese preserves semantic nuance."
        )
    }
}

# Standard I18N Pseudo-Localization Engine (Accented expansion for layout stress-testing)
PSEUDO_ACCENTS = {
    'a': 'å', 'b': 'ƀ', 'c': 'ç', 'd': 'ð', 'e': 'é', 'f': 'ƒ', 'g': 'ĝ',
    'h': 'ĥ', 'i': 'î', 'j': 'ĵ', 'k': 'ķ', 'l': 'ļ', 'm': 'ɱ', 'n': 'ñ',
    'o': 'ö', 'p': 'þ', 'q': 'ǫ', 'r': 'ŕ', 's': 'š', 't': 'ţ', 'u': 'û',
    'v': 'ṽ', 'w': 'ŵ', 'x': 'ẋ', 'y': 'ý', 'z': 'ž',
    'A': 'Å', 'B': 'Ɓ', 'C': 'Ç', 'D': 'Ð', 'E': 'É', 'F': 'Ƒ', 'G': 'Ĝ',
    'H': 'Ĥ', 'I': 'Î', 'J': 'Ĵ', 'K': 'Ķ', 'L': 'Ļ', 'M': 'Ṁ', 'N': 'Ñ',
    'O': 'Ö', 'P': 'Þ', 'Q': 'Ǫ', 'R': 'Ŕ', 'S': 'Š', 'T': 'Ţ', 'U': 'Û',
    'V': 'Ṽ', 'W': 'Ŵ', 'X': 'Ẋ', 'Y': 'Ý', 'Z': 'Ž'
}

def generate_pseudoloc_variants(source_text: str, target_locale: str) -> TranslationVariants:
    """
    Standard Internationalization (i18n) Pseudo-Localization:
    Emulates length expansion (+35%) and diacritic glyph rendering without destroying words.
    For RTL locales, embeds bidirectional isolate markers.
    """
    is_rtl = target_locale.lower().startswith(("ar", "ur", "he", "fa"))
    transformed = "".join(PSEUDO_ACCENTS.get(c, c) for c in source_text)

    # Standard: +35% expansion using trailing tildes, enclosed in brackets
    pad_len = max(3, int(len(source_text) * 0.35))
    expansion_pad = " ~" * (pad_len // 2)

    if is_rtl:
        # RTL pseudo-localization: isolate runes with RTL direction indicator
        std = f"\u2067[!! {transformed}{expansion_pad} !!]\u2069"
        cmp = f"\u2067[! {transformed} !]\u2069"
        ult = f"\u2067[{transformed}]\u2069"
    else:
        std = f"[!! {transformed}{expansion_pad} !!]"
        cmp = f"[! {transformed} !]"
        ult = f"[{transformed}]"

    return TranslationVariants(
        standard=std,
        compact=cmp,
        ultra_short=ult,
        cultural_notes=f"Pseudo-localized stress test (+35% expansion for {target_locale}). Set OPENAI_API_KEY in .env for neural translation."
    )

class LLMTranslator:
    def __init__(self):
        self._client: Optional[Any] = None

    def get_client(self) -> Optional[Any]:
        key = os.getenv("OPENAI_API_KEY")
        if not key:
            try:
                from dotenv import load_dotenv
                load_dotenv()
                key = os.getenv("OPENAI_API_KEY")
            except Exception:
                pass

        if key and (not self._client or getattr(self._client, "api_key", None) != key):
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=key)
            except ImportError:
                return None
        return self._client

    def translate_with_variants(
        self,
        source_text: str,
        source_locale: str,
        target_locale: str,
        glossary: Optional[Dict[str, str]] = None,
        bypass_presets: bool = False,
        mode: str = "local"
    ) -> Tuple[TranslationVariants, str]:
        clean_key = source_text.strip().lower()
        clean_locale = target_locale.lower().replace("_", "-")

        # 0. Identity pass-through for source locale (e.g. en-US)
        if clean_locale.startswith("en"):
            return TranslationVariants(
                standard=source_text,
                compact=source_text,
                ultra_short=source_text,
                cultural_notes="Source locale baseline."
            ), "PRESET"

        # 1. Check offline high-quality presets first (unless bypass_presets is explicitly enabled)
        if not bypass_presets:
            if clean_key in PRESET_TRANSLATIONS and clean_locale in PRESET_TRANSLATIONS[clean_key]:
                return PRESET_TRANSLATIONS[clean_key][clean_locale], "PRESET"

        # 2. External OpenAI API is strictly opt-in (mode == "openai" or bypass_presets == True)
        #    When mode == "local" (CLI default), zero website text ever leaves the machine.
        if mode == "openai" or bypass_presets:
            client = self.get_client()
            if client:
                try:
                    system_prompt = (
                        "You are a layout-aware localization engine. Translate the given UI string into the target locale.\n"
                        "CRITICAL QUALITY RULES:\n"
                        "- Never translate into English or prepend brackets like '[de-DE]'. Output authentic target language script.\n"
                        "- Never truncate full sentences down to a single word. Maintain complete semantic integrity across all 3 variants.\n"
                        "- Preserve all numbers, currency signs ($), variables, and brand names.\n\n"
                        "Variant guidelines:\n"
                        "1. standard: Idiomatic, polite, natural translation.\n"
                        "2. compact: Tighter phrasing dropping redundant articles or using concise synonyms, strictly preserving meaning.\n"
                        "3. ultra_short: Minimalist button action verb or concise summary phrase. Never orphan a noun or omit negation."
                    )
                    if glossary:
                        system_prompt += f"\nLocked customer glossary terms:\n{json.dumps(glossary, ensure_ascii=False)}"

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
                    parsed = completion.choices[0].message.parsed
                    if parsed:
                        return parsed, "OPENAI_API"
                except Exception as e:
                    print(f"[LLMTranslator] OpenAI call failed: {e}. Falling back to pseudo-localization.")
                    return generate_pseudoloc_variants(source_text, target_locale), "FALLBACK"

        # 3. Local Fallback: Standard I18N Pseudo-Localization Engine (100% local, zero external network calls)
        return generate_pseudoloc_variants(source_text, target_locale), "PSEUDO"

    def generate_variants_with_provenance(
        self,
        source_text: str,
        target_locale: str,
        element_type: str = "span",
        bypass_presets: bool = False,
        mode: str = "local"
    ) -> Tuple[Dict[str, str], str]:
        variants, prov = self.translate_with_variants(
            source_text=source_text,
            source_locale="en-US",
            target_locale=target_locale,
            bypass_presets=bypass_presets,
            mode=mode
        )
        return {
            "standard": variants.standard,
            "compact": variants.compact,
            "ultra_short": variants.ultra_short
        }, prov

llm_engine = LLMTranslator()
