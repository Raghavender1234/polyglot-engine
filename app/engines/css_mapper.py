from ..models import CSSRules

def get_css_rules(locale: str, font_size_px: float = 14.0) -> CSSRules:
    loc = locale.lower().replace("_", "-")

    if loc.startswith("ur"):
        line_height_val = 1.85
        return CSSRules(
            dir="rtl",
            classes="rtl-mode urdu-mode",
            font_family="'Noto Nastaliq Urdu', serif",
            line_height=str(line_height_val),
            letter_spacing="0px",
            recommended_min_height_px=round(font_size_px * line_height_val + 8, 1)
        )
    elif loc.startswith(("ar", "fa", "ps", "ug")):
        line_height_val = 1.5
        return CSSRules(
            dir="rtl",
            classes="rtl-mode arabic-mode",
            font_family="'Noto Sans Arabic', sans-serif",
            line_height=str(line_height_val),
            letter_spacing="0px",
            recommended_min_height_px=round(font_size_px * line_height_val + 6, 1)
        )
    elif loc.startswith("he"):
        line_height_val = 1.35
        return CSSRules(
            dir="rtl",
            classes="rtl-mode hebrew-mode",
            font_family="'Noto Sans Hebrew', sans-serif",
            line_height=str(line_height_val),
            letter_spacing="normal",
            recommended_min_height_px=round(font_size_px * line_height_val + 4, 1)
        )
    elif loc.startswith("ja"):
        line_height_val = 1.4
        return CSSRules(
            dir="ltr",
            classes="ltr-mode cjk-mode japanese-mode",
            font_family="'Noto Sans JP', sans-serif",
            line_height=str(line_height_val),
            letter_spacing="normal",
            recommended_min_height_px=round(font_size_px * line_height_val + 4, 1)
        )
    elif loc.startswith("zh"):
        line_height_val = 1.4
        return CSSRules(
            dir="ltr",
            classes="ltr-mode cjk-mode chinese-mode",
            font_family="'Noto Sans SC', sans-serif",
            line_height=str(line_height_val),
            letter_spacing="normal",
            recommended_min_height_px=round(font_size_px * line_height_val + 4, 1)
        )
    else:
        line_height_val = 1.25
        return CSSRules(
            dir="ltr",
            classes="ltr-mode",
            font_family="'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
            line_height=str(line_height_val),
            letter_spacing="normal",
            recommended_min_height_px=round(font_size_px * line_height_val + 4, 1)
        )
