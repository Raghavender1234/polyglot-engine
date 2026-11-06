"""
Polyglot Diagnosis — Computed Layout Constraint & Root-Cause Classifier
Analyzes computed CSS properties, flex/grid hierarchies, and text properties to explain WHY a layout failure occurred.
"""

from typing import Dict, Any, List
import re

class RootCauseDiagnoser:
    @staticmethod
    def diagnose_overflow(element: Dict[str, Any], overflow_px: float, locale: str) -> Dict[str, Any]:
        is_rtl = locale.lower().startswith(("ar", "ur", "he", "fa"))
        text = element.get("text", "")
        has_mixed_bidi = bool(re.search(r'[\$\d\%\+\-\/\#]', text)) and is_rtl

        parent_display = element.get("parentDisplay", "")
        parent_wrap = element.get("parentFlexWrap", "")
        is_rigid = element.get("isRigidWidth", False)
        width = element.get("contentWidth", 0)

        if has_mixed_bidi:
            return {
                "category": "BIDI_DIRECTIONAL_ISOLATION",
                "explanation": f"Mixed directional characters in {locale} causing punctuation and currency inversion.",
                "remedy": "Wrap text with Unicode isolation marks (\\u2066...\\u2069) and set dir='rtl'."
            }

        if parent_display == "flex" and parent_wrap in ("nowrap", ""):
            return {
                "category": "FLEX_CONTAINER_NO_WRAP",
                "explanation": f"Parent flex container forbids wrapping (flex-wrap: {parent_wrap or 'nowrap'}), causing expanding child to overflow or push siblings.",
                "remedy": "Allow container flex-wrapping or provide responsive minimum gap."
            }

        if is_rigid or (width > 0 and width < 90.0):
            return {
                "category": "CSS_RIGID_WIDTH_CONSTRAINT",
                "explanation": f"Element is constrained to a fixed {width:.0f}px box, which cannot accommodate standard vocabulary in {locale}.",
                "remedy": f"Set 'min-width: {width + overflow_px + 12:.0f}px; flex-shrink: 0;' or use fit-content."
            }

        return {
            "category": "TEXT_VERBOSITY_EXPANSION",
            "explanation": f"Linguistic expansion in {locale} exceeds container by +{overflow_px:.1f}px.",
            "remedy": "Swap to semantic compact variant or allow text wrapping."
        }

    @staticmethod
    def diagnose_collision(collision: Dict[str, Any], elem1: Dict[str, Any], elem2: Dict[str, Any]) -> Dict[str, Any]:
        p_display1 = elem1.get("parentDisplay", "") if elem1 else ""
        p_wrap1 = elem1.get("parentFlexWrap", "") if elem1 else ""

        if p_display1 == "flex" and p_wrap1 in ("nowrap", ""):
            return {
                "category": "FLEX_SIBLING_OVERLAP",
                "explanation": f"Adjacent elements in a non-wrapping flex layout overlapped by {collision['overlapArea']}px² when text expanded.",
                "remedy": "Enable flex-wrap on parent or reduce action button padding."
            }

        return {
            "category": "ABSOLUTE_OR_FIXED_OVERLAP",
            "explanation": f"Elements physically overlapped in DOM ({collision['overlapX']}px horizontal, {collision['overlapY']}px vertical).",
            "remedy": "Increase sibling margin or apply compact translation variant."
        }
