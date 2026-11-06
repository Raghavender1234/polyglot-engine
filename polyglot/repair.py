"""
Polyglot Repair — Multi-Candidate Backtracking & Closed-Loop Repair Engine
Executes a multi-candidate search loop:
  Candidate 1: standard
  Candidate 2: compact (if Candidate 1 overflows/collides)
  Candidate 3: ultra_short (if Candidate 2 overflows/collides)
  Candidate 4: targeted dynamic CSS injection (if text reduction cannot resolve without semantic loss)
"""

from typing import Dict, Any, List, Tuple
from .detector import CollisionDetector
from .diagnosis import RootCauseDiagnoser
from .patcher import DynamicCSSPatcher

JS_APPLY_BATCH_TEXT = """
(translations) => {
    function findTargetTextNode(element) {
        const explicitTextEl = element.querySelector('[data-polyglot-text]') || (element.hasAttribute('data-polyglot-text') ? element : null);
        if (explicitTextEl) {
            const walker = document.createTreeWalker(explicitTextEl, NodeFilter.SHOW_TEXT, null, false);
            let n;
            while ((n = walker.nextNode())) {
                if (n.textContent.trim().length > 0) return n;
            }
        }
        for (let i = 0; i < element.childNodes.length; i++) {
            const child = element.childNodes[i];
            if (child.nodeType === Node.TEXT_NODE && child.textContent.trim().length > 0) return child;
        }
        const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT, null, false);
        let target = null, maxLen = 0, node;
        while ((node = walker.nextNode())) {
            const trimmed = node.textContent.trim();
            if (trimmed.length > maxLen) {
                maxLen = trimmed.length;
                target = node;
            }
        }
        return target;
    }

    for (const item of translations) {
        const el = document.querySelector('[data-polyglot-id="' + item.id + '"]');
        if (!el) continue;

        const textNode = findTargetTextNode(el);
        if (textNode) {
            textNode.textContent = item.text;
        } else {
            el.textContent = item.text;
        }

        if (item.dir) el.dir = item.dir;
    }

    void document.body.offsetHeight;
    return true;
}
"""

JS_INJECT_CSS_PATCH = """
(cssText) => {
    let styleEl = document.getElementById('polyglot-dynamic-repair-patch');
    if (!styleEl) {
        styleEl = document.createElement('style');
        styleEl.id = 'polyglot-dynamic-repair-patch';
        document.head.appendChild(styleEl);
    }
    styleEl.textContent = cssText;
    void document.body.offsetHeight;
    return true;
}
"""

class RepairOrchestrator:
    def __init__(self, page, target_elements: List[Dict[str, Any]], candidates_map: Dict[str, Dict[str, Any]], locale: str):
        self.page = page
        self.elements = target_elements
        self.candidates = candidates_map
        self.locale = locale
        self.target_ids = [el["id"] for el in target_elements]

    def execute_closed_loop_repair(self) -> Dict[str, Any]:
        """
        Executes real backtracking across length variants, then applies targeted dynamic CSS if needed.
        """
        # Pass 1: Apply 'standard' translations
        pass1_payload = []
        for el in self.elements:
            cand = self.candidates.get(el["id"], {})
            pass1_payload.append({
                "id": el["id"],
                "text": cand.get("standard", el["text"]),
                "dir": cand.get("dir", "")
            })

        self.page.evaluate(JS_APPLY_BATCH_TEXT, pass1_payload)
        metrics_pass1 = CollisionDetector.detect(self.page, self.target_ids)
        initial_overflows = metrics_pass1["overflowCount"]
        initial_collisions = metrics_pass1["collisionCount"]

        failing_ids = set()
        for ovf in metrics_pass1["overflows"]:
            failing_ids.add(ovf["id"])
        for col in metrics_pass1["collisions"]:
            failing_ids.add(col["translatedId"])

        chosen_variants = {el["id"]: "standard" for el in self.elements}
        active_texts = {el["id"]: self.candidates.get(el["id"], {}).get("standard", el["text"]) for el in self.elements}

        # Pass 2: Backtrack to 'compact' for failing elements
        if failing_ids:
            pass2_payload = []
            for el_id in failing_ids:
                cand = self.candidates.get(el_id, {})
                compact_text = cand.get("compact")
                if compact_text and compact_text != active_texts[el_id]:
                    active_texts[el_id] = compact_text
                    chosen_variants[el_id] = "compact"
                    pass2_payload.append({
                        "id": el_id,
                        "text": compact_text,
                        "dir": cand.get("dir", "")
                    })

            if pass2_payload:
                self.page.evaluate(JS_APPLY_BATCH_TEXT, pass2_payload)
                metrics_pass2 = CollisionDetector.detect(self.page, self.target_ids)
                failing_ids = set([o["id"] for o in metrics_pass2["overflows"]] + [c["translatedId"] for c in metrics_pass2["collisions"]])

        # Pass 3: Backtrack to 'ultra_short' for still-failing elements
        if failing_ids:
            pass3_payload = []
            for el_id in failing_ids:
                cand = self.candidates.get(el_id, {})
                ultra_text = cand.get("ultra_short")
                if ultra_text and ultra_text != active_texts[el_id]:
                    active_texts[el_id] = ultra_text
                    chosen_variants[el_id] = "ultra_short"
                    pass3_payload.append({
                        "id": el_id,
                        "text": ultra_text,
                        "dir": cand.get("dir", "")
                    })

            if pass3_payload:
                self.page.evaluate(JS_APPLY_BATCH_TEXT, pass3_payload)
                metrics_pass3 = CollisionDetector.detect(self.page, self.target_ids)
                failing_ids = set([o["id"] for o in metrics_pass3["overflows"]] + [c["translatedId"] for c in metrics_pass3["collisions"]])

        # Pass 4: Dynamic Targeted CSS Repair for remaining rigid layout failures
        diagnosed_issues = []
        applied_css = ""

        if failing_ids:
            el_map = {el["id"]: el for el in self.elements}
            final_check = CollisionDetector.detect(self.page, self.target_ids)

            for ovf in final_check["overflows"]:
                el = el_map.get(ovf["id"])
                if el:
                    diag = RootCauseDiagnoser.diagnose_overflow(el, ovf["overflowPx"], self.locale)
                    diag["selector"] = el.get("selector", "")
                    diag["current_width"] = el.get("contentWidth", 60.0)
                    diag["overflow_px"] = ovf["overflowPx"]
                    diagnosed_issues.append(diag)

            for col in final_check["collisions"]:
                el = el_map.get(col["translatedId"])
                if el:
                    diag = RootCauseDiagnoser.diagnose_collision(col, el, {})
                    diag["selector"] = el.get("selector", "")
                    diag["current_width"] = el.get("contentWidth", 60.0)
                    diag["overflow_px"] = col["overlapX"]
                    diagnosed_issues.append(diag)

            if diagnosed_issues:
                applied_css = DynamicCSSPatcher.generate_css(diagnosed_issues)
                self.page.evaluate(JS_INJECT_CSS_PATCH, applied_css)

        # Final Verification
        final_metrics = CollisionDetector.detect(self.page, self.target_ids)
        final_overflows = final_metrics["overflowCount"]
        final_collisions = final_metrics["collisionCount"]

        return {
            "initial_overflows": initial_overflows,
            "initial_collisions": initial_collisions,
            "final_overflows": final_overflows,
            "final_collisions": final_collisions,
            "resolved_overflows": max(0, initial_overflows - final_overflows),
            "resolved_collisions": max(0, initial_collisions - final_collisions),
            "diagnosed_issues": diagnosed_issues,
            "dynamic_css": applied_css,
            "chosen_variants": chosen_variants,
            "active_texts": active_texts,
            "all_cleared": (final_overflows == 0 and final_collisions == 0)
        }
