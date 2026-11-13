"""
Polyglot Visual AI — Layer 2 Visual Verification (Moondream)

Strict Privacy-First Mode Separation:
- `off` (default): Deterministic Playwright geometry checks only (0ms AI overhead, 100% local).
- `local`: Strictly local model inference ONLY (loads local HuggingFace `vikhyatk/moondream2` weights via
  `transformers`/`torch` or queries a local Ollama daemon at `127.0.0.1`).
  NEVER sends screenshots over the internet and NEVER falls back to a cloud API.
  Raises a clear `RuntimeError` if no local inference runtime is available.
- `api`: Explicitly opt-in cloud inference (`https://api.moondream.ai/v1/query`). Requires `MOONDREAM_API_KEY`.
- `mock`: Deterministic offline test adapter for unit testing.
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
    """Layer 2 Visual AI Inspector with strict local vs. cloud separation and dual-sampling."""

    VALID_MODES = ("off", "local", "api", "mock")

    def __init__(
        self,
        mode: str = "off",
        api_key: Optional[str] = None,
        endpoint: Optional[str] = None,
        model_id: str = "vikhyatk/moondream2",
        clean_sample_size: int = 5
    ):
        normalized = (mode or "off").lower().strip()
        if normalized not in self.VALID_MODES:
            raise ValueError(
                f"Invalid visual_ai mode '{mode}'. Choose from {self.VALID_MODES}. "
                "Note: 'local' is strictly on-device; 'api' is explicit cloud opt-in."
            )
        self.mode = normalized
        self.api_key = api_key or os.getenv("MOONDREAM_API_KEY", "")
        self.endpoint = endpoint
        self.model_id = model_id
        self.clean_sample_size = clean_sample_size

        self._hf_model = None
        self._hf_tokenizer = None
        self._local_backend: Optional[str] = None

        if self.mode == "local":
            self._init_strictly_local_runtime()
        elif self.mode == "api":
            if not self.api_key:
                raise RuntimeError(
                    "Visual AI mode 'api' requires MOONDREAM_API_KEY to be set. "
                    "For privacy-first local inference, use --visual-ai=local."
                )

    def _init_strictly_local_runtime(self) -> None:
        """Initializes a strictly local Moondream inference runtime.
        Checks (1) local Ollama daemon on loopback (127.0.0.1 / localhost), or
        (2) local HuggingFace transformers + torch weights.
        Fails explicitly if neither is available; NEVER falls back to cloud.
        """
        local_url = self.endpoint or "http://127.0.0.1:11434/api/generate"
        if not (local_url.startswith("http://127.0.0.1") or local_url.startswith("http://localhost")):
            raise RuntimeError(
                f"Privacy violation prevented: --visual-ai=local refuses non-loopback endpoint '{local_url}'."
            )

        # 1. Check if local Ollama daemon is reachable on loopback AND has moondream model pulled
        tags_url = local_url.replace("/api/generate", "/api/tags")
        try:
            req = urllib.request.Request(tags_url, method="GET")
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    models = [m.get("name", "") for m in data.get("models", [])]
                    # Check if moondream or any variant (e.g. moondream:latest) is installed
                    has_moondream = any("moondream" in m.lower() for m in models)
                    if has_moondream:
                        self._local_backend = "ollama_loopback"
                        self.endpoint = local_url
                        return
                    else:
                        print(
                            f"[VisualAI] Local Ollama daemon detected at {local_url}, but 'moondream' model is not installed.\n"
                            f"Available models in Ollama: {models or 'None'}.\n"
                            f"Action required: Run `ollama pull moondream` in your terminal."
                        )
        except Exception:
            pass

        # 2. Check if local transformers + torch are installed for in-process weights
        try:
            import torch  # noqa: F401
            from transformers import AutoModelForCausalLM, AutoTokenizer
            self._hf_tokenizer = AutoTokenizer.from_pretrained(self.model_id, trust_remote_code=True)
            self._hf_model = AutoModelForCausalLM.from_pretrained(
                self.model_id, trust_remote_code=True
            )
            self._hf_model.eval()
            self._local_backend = "transformers_local"
            return
        except Exception as e:
            raise RuntimeError(
                "Cannot initialize --visual-ai=local: No local inference runtime found. "
                "Either start a local Ollama instance (`ollama run moondream` on 127.0.0.1:11434) "
                "or install local model dependencies (`pip install \"polyglot-engine[visual]\"`). "
                f"Silent cloud fallback is disabled by design. Underlying error: {e}"
            ) from e

    @property
    def is_enabled(self) -> bool:
        return self.mode != "off"

    def select_candidates(
        self,
        target_elements: List[Dict[str, Any]],
        flagged_ids: Set[str]
    ) -> List[Dict[str, Any]]:
        """Dual-sampling strategy for Enhanced Mode:
        1. All elements flagged by deterministic geometry checks.
        2. Up to `clean_sample_size` elements that PASSED geometry checks (prioritizing
           buttons and RTL elements) to catch visual defects DOM geometry misses.
        """
        flagged: List[Dict[str, Any]] = []
        clean_pool: List[Dict[str, Any]] = []

        for el in target_elements:
            if str(el.get("id")) in flagged_ids:
                flagged.append(el)
            else:
                clean_pool.append(el)

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
        """Evaluates an isolated component PNG screenshot using the selected mode."""
        start = time.perf_counter()

        if self.mode == "mock":
            text = (element_meta or {}).get("text", "")
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

        if self.mode == "local":
            if self._local_backend == "transformers_local" and self._hf_model is not None:
                from PIL import Image
                img = Image.open(io.BytesIO(png_bytes))
                enc_image = self._hf_model.encode_image(img)
                ans = self._hf_model.answer_question(enc_image, VISUAL_PROMPT, self._hf_tokenizer)
                parsed = self._parse_json_safely(ans)
                return VisualResult(
                    defect=bool(parsed.get("defect", False)),
                    defect_type=parsed.get("defect_type"),
                    confidence=float(parsed.get("confidence", 0.5)),
                    reason=str(parsed.get("reason", "")),
                    latency_ms=round((time.perf_counter() - start) * 1000, 2)
                )
            elif self._local_backend == "ollama_loopback":
                b64_img = base64.b64encode(png_bytes).decode("utf-8")
                payload = {
                    "model": "moondream",
                    "prompt": VISUAL_PROMPT,
                    "images": [b64_img],
                    "stream": False,
                    "format": "json"
                }
                req = urllib.request.Request(
                    self.endpoint,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"}
                )
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
            raise RuntimeError("Local Visual AI backend not initialized.")

        if self.mode == "api":
            b64_img = base64.b64encode(png_bytes).decode("utf-8")
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
