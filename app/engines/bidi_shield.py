import re

# Unicode Directional Formatting Characters
LRI = "\u2066"  # LEFT-TO-RIGHT ISOLATE
RLI = "\u2067"  # RIGHT-TO-LEFT ISOLATE
FSI = "\u2068"  # FIRST STRONG ISOLATE
PDI = "\u2069"  # POP DIRECTIONAL ISOLATE
ZWSP = "\u200B" # ZERO-WIDTH SPACE (for CJK / Thai word break hints)

# Pattern matching LTR islands:
# 1. Currency & Prices: e.g. $49.99, 49.99$, €10, 100€
# 2. Version strings: v2.1, 1.0.0
# 3. Numeric values, phone numbers, codes
# 4. Latin words/brands: e.g. Apple, PayPal, API, URL
LTR_ISLAND_PATTERN = re.compile(
    r"("
    r"[\$€£¥₹]\s*\d+(?:[.,]\d+)?|"   # Currency prefix: $49.99
    r"\d+(?:[.,]\d+)?\s*[\$€£¥₹]|"   # Currency suffix: 49.99$
    r"[a-zA-Z0-9_\-\.\:\/]+|"        # Latin words, URLs, versions, numbers
    r"\d+(?:[.,\-]\d+)*"             # Numbers
    r")"
)

# Detect if locale is RTL
def is_rtl_locale(locale: str) -> bool:
    loc = locale.lower().replace("_", "-")
    return loc.startswith(("ar", "ur", "he", "fa", "ps", "sd", "ug"))

def is_cjk_locale(locale: str) -> bool:
    loc = locale.lower().replace("_", "-")
    return loc.startswith(("ja", "zh", "ko"))

def is_thai_locale(locale: str) -> bool:
    loc = locale.lower().replace("_", "-")
    return loc.startswith("th")

def shield_bidi_text(text: str, locale: str) -> str:
    """
    Protects text rendering in BiDi contexts.
    For RTL locales:
      - Isolates embedded LTR fragments (prices, versions, brands) using \\u2066...\\u2069.
      - Wraps outer text with \\u2067...\\u2069 to prevent trailing punctuation inversion.
    For CJK/Thai:
      - Optionally inserts zero-width word break tags (\\u200B) where appropriate.
    For LTR locales:
      - Preserves standard formatting.
    """
    if not is_rtl_locale(locale):
        if is_cjk_locale(locale):
            # For CJK, replace punctuation spacing with ZWSP if needed
            return text
        return text

    # It's an RTL locale. Let's isolate LTR islands within Arabic/Urdu/Hebrew
    def isolate_ltr(match):
        token = match.group(0).strip()
        if not token:
            return match.group(0)
        # Avoid double isolation
        if token.startswith(LRI) and token.endswith(PDI):
            return token
        return f"{LRI}{token}{PDI}"

    # Replace numbers, currencies, latin words with LTR isolates
    isolated_inner = LTR_ISLAND_PATTERN.sub(isolate_ltr, text)

    # Wrap the entire expression in an RLI ... PDI boundary to anchor directionality
    safe_text = f"{RLI}{isolated_inner}{PDI}"
    return safe_text
