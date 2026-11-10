"""
Polyglot Visual AI — Optional Layer 2 Visual Verification (Moondream 3.1 / 2)

Implements two explicit modes as designed:
- Standard Mode (`off`, default): Pure Playwright deterministic geometry checks (0ms AI overhead).
- Enhanced Mode (`moondream`, `moondream3_api`, `ollama`, `openai_compat`, `mock`):
  Runs Playwright geometry checks first, then uses Moondream on cropped element screenshots for:
  1. Elements flagged by deterministic geometry checks (confirming visual severity).
  2. A sample of elements that PASSED geometry checks (catching defects DOM geometry misses,
     such as text visually colliding with an icon whose bounding box doesn't intersect,
     bad font rendering, or displaced Arabic punctuation).
"""

from __future__ import annotations

import base64
import io
import json
import os
import time
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set


VISUAL_PROMPT = """You are an expert visual UI defect inspector.
Analyze this cropped screenshot of a UI component (button, badge, tab, or label).
Determine if there is a visual defect:
1. "text_clipped": Text cut off by borders, truncated prematurely, or clipped ascenders/descenders.
2. "text_icon_overlap": Text visually colliding with or overlapping an icon, badge, or symbol.
3. "bidi_inversion": Arabic/Hebrew text where numbers, currency, or punctuation look visually misplaced.
4. "font_illegibility": Font renders badly or is unreadable despite fitting inside its container.

NOTE: Intentional tight padding that does NOT cut off characters, clean 2-line wrapping, and valid RTL numbers are NOT defects.

Return strictly a JSON object:
{
  "defect": true or false,
  "defect_type": "text_clipped" | "text_icon_overlap" | "bidi_inversion" | "font_illegibility" | null,
  "confidence": 0.0 to 1.0,
  "reason": "Brief explanation"
}
"""


@dataclass
class VisualResult:
    defect: bool
    defect_type: Optional[str]
    confidence: float
    reason: str
    latency_ms: float


class VisualAIInspector:
    """Layer 2 Visual AI Inspector with dual-sampling (flagged + geometry-clean sample)."""

    def __init__(
        self,
        mode: str = "off",
        api_key: Optional[str] = None,
        endpoint: Optional[str] = None,
        clean_sample_size: int = 5
    ):
        self.mode = (mode or "off").lower().strip()
        self.api_key = api_key or os.getenv("MOONDREAM_API_KEY", "")
        self.endpoint = endpoint
        self.clean_sample_size = clean_sample_size
        self._local_md_model = None

        if self.mode == "moondream":
            # Try loading official `moondream` python SDK if installed via `pip install polyglot-engine[visual]`
            try:
                import moondream as md
                if self.api_key:
                    self._local_md_model = md.vl(api_key=self.api_key)
            except ImportError:
                self._local_md_model = None

    @property
    def is_enabled(self) -> bool:
        return self.mode not in ("off", "none", "false", "")

    def select_candidates(
        self,
        target_elements: List[Dict[str, Any]],
        flagged_ids: Set[str]
    ) -> List[Dict[str, Any]]:
        """Dual-sampling strategy for Enhanced Mode:
        1. Select all elements flagged by deterministic geometry checks.
        2. Select up to `clean_sample_size` elements that PASSED geometry checks,
           prioritizing buttons/interactive controls and RTL elements to catch visual
           defects that DOM bounding boxes miss.
        """
        flagged: List[Dict[str, Any]] = []
        clean_pool: List[Dict[str, Any]] = []

        for el in target_elements:
            if str(el.get("id")) in flagged_ids:
                flagged.append(el)
            else:
                clean_pool.append(el)

        # Prioritize interactive elements (buttons, tabs) and RTL elements in the clean sample
        def _priority_key(e: Dict[str, Any]) -> int:
            score = 0
            if e.get("tag") in ("button", "a") or e.get("elementType") == "button":
                score += 2
            if e.get("direction") == "rtl":
                score += 2
            return -score

        clean_pool.sort(key=_priority_key)
        sampled_clean = clean_pool[: self.clean_sample_size]
        return flagged + sampled_clean

    def inspect_crop(self, png_bytes: bytes, element_meta: Optional[Dict[str, Any]] = None) -> VisualResult:
        """Evaluates an isolated component PNG screenshot using the configured Moondream backend."""
        start = time.perf_counter()
        b64_img = base64.b64encode(png_bytes).decode("utf-8")

        if self.mode == "mock":
            text = (element_meta or {}).get("text", "")
            # Mock logic for deterministic unit testing
            is_def = "OVERLAP_ICON" in text or "VISUAL_BROKEN" in text
            dtype = "text_icon_overlap" if is_def else None
            reason = "Text visually overlaps adjacent icon inside button." if is_def else "Component appears visually clean."
            return VisualResult(
                defect=is_def,
                defect_type=dtype,
                confidence=0.91 if is_def else 0.89,
                reason=reason,
                latency_ms=round((time.perf_counter() - start) * 1000 + 12.0, 2)
            )

        if self._local_md_model is not None:
            try:
                from PIL import Image
                img = Image.open(io.BytesIO(png_bytes))
                ans = self._local_md_model.query(img, VISUAL_PROMPT).get("answer", "{}")
                parsed = self._parse_json_safely(ans)
                return VisualResult(
                    defect=bool(parsed.get("defect", False)),
                    defect_type=parsed.get("defect_type"),
                    confidence=float(parsed.get("confidence", 0.5)),
                    reason=str(parsed.get("reason", "")),
                    latency_ms=round((time.perf_counter() - start) * 1000, 2)
                )
            except Exception as e:
                return VisualResult(False, None, 0.0, f"Moondream SDK error: {e}", 0.0)

        if self.mode in ("moondream", "moondream3_api"):
            url = self.endpoint or "https://api.moondream.ai/v1/query"
            payload = {
                "image_url": f"data:image/png;base64,{b64_img}",
                "question": VISUAL_PROMPT,
                "stream": False
            }
            headers = {
                "Content-Type": "application/json",
                "X-Moondream-Auth": self.api_key
            }
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=25) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    parsed = self._parse_json_safely(data.get("answer", "{}"))
                    return VisualResult(
                        defect=bool(parsed.get("defect", False)),
                        defect_type=parsed.get("defect_type"),
                        confidence=float(parsed.get("confidence", 0.5)),
                        reason=str(parsed.get("reason", "")),
                        latency_ms=round((time.perf_counter() - start) * 1000, 2)
                    )
            except Exception as e:
                return VisualResult(False, None, 0.0, f"Moondream API error: {e}", 0.0)

        if self.mode == "ollama":
            url = self.endpoint or "http://localhost:11434/api/generate"
            payload = {
                "model": "moondream",
                "prompt": VISUAL_PROMPT,
                "images": [b64_img],
                "stream": False,
                "format": "json"
            }
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=25) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    parsed = self._parse_json_safely(data.get("response", "{}"))
                    return VisualResult(
                        defect=bool(parsed.get("defect", False)),
                        defect_type=parsed.get("defect_type"),
                        confidence=float(parsed.get("confidence", 0.5)),
                        reason=str(parsed.get("reason", "")),
                        latency_ms=round((time.perf_counter() - start) * 1000, 2)
                    )
            except Exception as e:
                return VisualResult(False, None, 0.0, f"Ollama error: {e}", 0.0)

        return VisualResult(False, None, 0.0, "Visual AI disabled", 0.0)

    def inspect_page(
        self,
        page: Any,
        target_elements: List[Dict[str, Any]],
        flagged_ids: Set[str]
    ) -> List[Dict[str, Any]]:
        """Captures cropped screenshots for dual-sampled elements and returns newly identified visual issues."""
        if not self.is_enabled:
            return []

        candidates = self.select_candidates(target_elements, flagged_ids)
        visual_issues: List[Dict[str, Any]] = []

        for el in candidates:
            el_id = str(el.get("id"))
            try:
                loc = page.locator(f'[data-polyglot-id="{el_id}"]')
                if loc.count() == 0:
                    continue
                png_bytes = loc.first.screenshot()
                res = self.inspect_crop(png_bytes, element_meta=el)
                if res.defect:
                    dtype = (res.defect_type or "visual_defect").upper()
                    visual_issues.append({
                        "id": el_id,
                        "selector": el.get("selector", el.get("tag", "element")),
                        "category": f"VISUAL_AI_{dtype}",
                        "explanation": f"[Moondream Visual AI (conf={res.confidence:.2f})] {res.reason}",
                        "remedy": "Increase internal padding/gap between icon and text or adjust font rendering.",
                        "text": el.get("text", ""),
                        "overflow_px": 0.0,
                        "confidence": res.confidence,
                        "caught_by_visual_ai_only": el_id not in flagged_ids
                    })
            except Exception:
                continue

        return visual_issues

    @staticmethod
    def _parse_json_safely(raw_text: str) -> Dict[str, Any]:
        cleaned = (raw_text or "{}").strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        try:
            return json.loads(cleaned)
        except Exception:
            return {"defect": False, "defect_type": None, "confidence": 0.0, "reason": raw_text[:120]}
