"""
Polyglot Repair — Multi-Candidate Backtracking & Closed-Loop Repair Engine
Executes configurable repair strategies:
  - "auto": Try candidate backtracking (compact -> ultra_short) first; if rigid layout failures persist, apply dynamic CSS layout repair.
  - "text-only": Only backtrack across linguistic length variants (no CSS overrides).
  - "css-only": Keep standard translations; resolve overflows and collisions exclusively via targeted CSS adjustments.
"""

import os
import subprocess
from typing import Dict, Any, List, Tuple, Optional
from .detector import CollisionDetector
from .diagnosis import RootCauseDiagnoser
from .patcher import DynamicCSSPatcher, GitDiffPatcher

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
    def __init__(
        self,
        page,
        target_elements: List[Dict[str, Any]],
        candidates_map: Dict[str, Dict[str, Any]],
        locale: str,
        strategy: str = "auto",
        verify: bool = True,
        repo_path: Optional[str] = None
    ):
        self.page = page
        self.elements = target_elements
        self.candidates = candidates_map
        self.locale = locale
        self.strategy = strategy.lower().strip()  # "auto", "css-only", "text-only"
        self.verify = verify
        self.repo_path = repo_path
        self.target_ids = [el["id"] for el in target_elements]

    def execute_closed_loop_repair(self) -> Dict[str, Any]:
        """
        Executes strategy-directed repair across translation candidates and dynamic CSS patches.
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
        initial_bidi_defects = metrics_pass1.get("bidiCount", 0)

        # Initial baseline diagnosis of all failures
        el_map = {el["id"]: el for el in self.elements}
        initial_diagnosed_issues = []
        seen_diag_ids = set()

        for ovf in metrics_pass1["overflows"]:
            el = el_map.get(ovf["id"], {})
            merged_el = {**el, **ovf}
            diag = RootCauseDiagnoser.diagnose_overflow(merged_el, ovf["overflowPx"], self.locale)
            diag["id"] = ovf["id"]
            diag["selector"] = ovf["selector"]
            diag["target_stylesheet"] = ovf.get("target_stylesheet")
            diag["current_width"] = ovf.get("computedWidth", el.get("contentWidth", 60.0))
            diag["overflow_px"] = ovf["overflowPx"]
            initial_diagnosed_issues.append(diag)
            seen_diag_ids.add(ovf["id"])

        for col in metrics_pass1["collisions"]:
            el = el_map.get(col["translatedId"], {})
            merged_el = {**el, **col}
            diag = RootCauseDiagnoser.diagnose_collision(col, merged_el, {})
            diag["id"] = col["translatedId"]
            diag["selector"] = col["selector1"]
            diag["target_stylesheet"] = col.get("target_stylesheet")
            diag["collided_with"] = col.get("selector2", "")
            diag["current_width"] = el.get("contentWidth", 60.0)
            diag["overflow_px"] = col["overlapX"]
            initial_diagnosed_issues.append(diag)
            seen_diag_ids.add(col["translatedId"])

            if col.get("otherTranslatedId") and col["otherTranslatedId"] in el_map and col["otherTranslatedId"] not in seen_diag_ids:
                el2 = el_map[col["otherTranslatedId"]]
                diag2 = RootCauseDiagnoser.diagnose_collision(col, el2, {})
                diag2["id"] = col["otherTranslatedId"]
                diag2["selector"] = col.get("selector2", "")
                diag2["target_stylesheet"] = col.get("target_stylesheet")
                diag2["collided_with"] = col.get("selector1", "")
                diag2["current_width"] = el2.get("contentWidth", 60.0)
                diag2["overflow_px"] = col["overlapX"]
                initial_diagnosed_issues.append(diag2)
                seen_diag_ids.add(col["otherTranslatedId"])

        for bidi in metrics_pass1.get("bidiIssues", []):
            diag = {
                "id": bidi.get("id"),
                "selector": bidi.get("selector"),
                "target_stylesheet": bidi.get("target_stylesheet"),
                "category": "BIDI_DIRECTIONAL_ISOLATION",
                "explanation": bidi.get("explanation"),
                "remedy": bidi.get("remedy"),
                "text": bidi.get("text"),
                "direction": bidi.get("direction"),
                "unicodeBidi": bidi.get("unicodeBidi"),
                "overflow_px": 0.0,
                "current_width": 60.0
            }
            initial_diagnosed_issues.append(diag)
            if bidi.get("id"):
                seen_diag_ids.add(bidi["id"])

        failing_ids = set()
        for ovf in metrics_pass1["overflows"]:
            failing_ids.add(ovf["id"])
        for col in metrics_pass1["collisions"]:
            failing_ids.add(col["translatedId"])
            if col.get("otherTranslatedId"):
                failing_ids.add(col["otherTranslatedId"])
        for bidi in metrics_pass1.get("bidiIssues", []):
            if bidi.get("id"):
                failing_ids.add(bidi["id"])

        chosen_variants = {el["id"]: "standard" for el in self.elements}
        active_texts = {el["id"]: self.candidates.get(el["id"], {}).get("standard", el["text"]) for el in self.elements}

        # Linguistic variant backtracking (allowed in "auto" and "text-only")
        if self.strategy in ("auto", "text-only") and failing_ids:
            # Pass 2: Backtrack to 'compact' for failing elements
            pass2_payload = []
            for el_id in list(failing_ids):
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
                failing_ids = set(
                    [o["id"] for o in metrics_pass2["overflows"]] +
                    [c["translatedId"] for c in metrics_pass2["collisions"]] +
                    [c["otherTranslatedId"] for c in metrics_pass2["collisions"] if c.get("otherTranslatedId")] +
                    [b["id"] for b in metrics_pass2.get("bidiIssues", []) if b.get("id")]
                )

            # Pass 3: Backtrack to 'ultra_short' for still-failing elements
            if failing_ids:
                pass3_payload = []
                for el_id in list(failing_ids):
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
                    failing_ids = set(
                        [o["id"] for o in metrics_pass3["overflows"]] +
                        [c["translatedId"] for c in metrics_pass3["collisions"]] +
                        [c["otherTranslatedId"] for c in metrics_pass3["collisions"] if c.get("otherTranslatedId")] +
                        [b["id"] for b in metrics_pass3.get("bidiIssues", []) if b.get("id")]
                    )

        # Dynamic CSS injection (allowed in "auto" and "css-only")
        diagnosed_issues = []
        applied_css = ""

        if self.strategy in ("auto", "css-only") and failing_ids:
            el_map = {el["id"]: el for el in self.elements}
            fresh_check = CollisionDetector.detect(self.page, self.target_ids)
            fresh_seen = set()

            for ovf in fresh_check["overflows"]:
                el = el_map.get(ovf["id"], {})
                # Merge fresh browser measurements
                merged_el = {**el, **ovf}
                diag = RootCauseDiagnoser.diagnose_overflow(merged_el, ovf["overflowPx"], self.locale)
                diag["id"] = ovf["id"]
                diag["selector"] = ovf["selector"]
                diag["target_stylesheet"] = ovf.get("target_stylesheet")
                diag["current_width"] = ovf.get("computedWidth", el.get("contentWidth", 60.0))
                diag["overflow_px"] = ovf["overflowPx"]
                diagnosed_issues.append(diag)
                fresh_seen.add(ovf["id"])

            for col in fresh_check["collisions"]:
                el = el_map.get(col["translatedId"], {})
                merged_el = {**el, **col}
                diag = RootCauseDiagnoser.diagnose_collision(col, merged_el, {})
                diag["id"] = col["translatedId"]
                diag["selector"] = col["selector1"]
                diag["target_stylesheet"] = col.get("target_stylesheet")
                diag["current_width"] = el.get("contentWidth", 60.0)
                diag["overflow_px"] = col["overlapX"]
                diagnosed_issues.append(diag)
                fresh_seen.add(col["translatedId"])

                if col.get("otherTranslatedId") and col["otherTranslatedId"] in el_map and col["otherTranslatedId"] not in fresh_seen:
                    el2 = el_map[col["otherTranslatedId"]]
                    diag2 = RootCauseDiagnoser.diagnose_collision(col, el2, {})
                    diag2["id"] = col["otherTranslatedId"]
                    diag2["selector"] = col.get("selector2", "")
                    diag2["target_stylesheet"] = col.get("target_stylesheet")
                    diag2["current_width"] = el2.get("contentWidth", 60.0)
                    diag2["overflow_px"] = col["overlapX"]
                    diagnosed_issues.append(diag2)
                    fresh_seen.add(col["otherTranslatedId"])

            for bidi in fresh_check.get("bidiIssues", []):
                diag = {
                    "id": bidi.get("id"),
                    "selector": bidi.get("selector"),
                    "target_stylesheet": bidi.get("target_stylesheet"),
                    "category": "BIDI_DIRECTIONAL_ISOLATION",
                    "explanation": bidi.get("explanation"),
                    "remedy": bidi.get("remedy"),
                    "text": bidi.get("text"),
                    "direction": bidi.get("direction"),
                    "unicodeBidi": bidi.get("unicodeBidi"),
                    "overflow_px": 0.0,
                    "current_width": 60.0
                }
                diagnosed_issues.append(diag)

            if diagnosed_issues:
                applied_css = DynamicCSSPatcher.generate_css(diagnosed_issues)
                self.page.evaluate(JS_INJECT_CSS_PATCH, applied_css)

        # Verification step
        source_patch_verified = False
        git_patch_text = None

        if self.verify:
            final_metrics = CollisionDetector.detect(self.page, self.target_ids)
            final_overflows = final_metrics["overflowCount"]
            final_collisions = final_metrics["collisionCount"]
            final_bidi_defects = final_metrics.get("bidiCount", 0)
            resolved_overflows = max(0, initial_overflows - final_overflows)
            resolved_collisions = max(0, initial_collisions - final_collisions)
            resolved_bidi_defects = max(0, initial_bidi_defects - final_bidi_defects)
            all_cleared = (final_overflows == 0 and final_collisions == 0 and final_bidi_defects == 0)
            verified_status = True

            # Closed-Loop Source Patch Verification if repo_path provided
            if self.repo_path and os.path.exists(self.repo_path):
                # Combine all diagnosed layout and BiDi issues so source stylesheets receive comprehensive protection
                merged_diag = {}
                for d in initial_diagnosed_issues:
                    if d.get("id"):
                        merged_diag[d["id"]] = d
                for d in diagnosed_issues:
                    if d.get("id"):
                        merged_diag[d["id"]] = d
                all_diagnosed = list(merged_diag.values()) if merged_diag else (diagnosed_issues or initial_diagnosed_issues)

                git_patch_text = GitDiffPatcher.generate_patch(self.repo_path, all_diagnosed)
                if git_patch_text:
                    try:
                        # 1. Apply patch to clean source repo
                        proc = subprocess.run(
                            ["git", "apply", "--ignore-whitespace"],
                            input=git_patch_text,
                            text=True,
                            cwd=self.repo_path,
                            capture_output=True
                        )
                        if proc.returncode == 0:
                            # 2. Remove in-memory dynamic CSS overrides completely
                            self.page.evaluate("() => { const s = document.getElementById('polyglot-dynamic-repair-patch'); if (s) s.remove(); }")
                            # 3. Reload page from disk
                            self.page.reload(wait_until="domcontentloaded")
                            self.page.wait_for_timeout(300)
                            # 4. Re-apply localized text state
                            reapply_payload = [
                                {"id": el_id, "text": active_texts.get(el_id, ""), "dir": self.candidates.get(el_id, {}).get("dir", "")}
                                for el_id in self.target_ids
                            ]
                            self.page.evaluate(JS_APPLY_BATCH_TEXT, reapply_payload)
                            self.page.wait_for_timeout(200)

                            # 5. Measure on freshly reloaded page with ONLY the on-disk patch active!
                            src_metrics = CollisionDetector.detect(self.page, self.target_ids)
                            if (src_metrics["overflowCount"] == 0 and
                                src_metrics["collisionCount"] == 0 and
                                src_metrics.get("bidiCount", 0) == 0):
                                source_patch_verified = True
                    except Exception as e:
                        print(f"⚠️ Closed-loop source patch verification error: {e}")
        else:
            final_overflows = None
            final_collisions = None
            final_bidi_defects = None
            resolved_overflows = None
            resolved_collisions = None
            resolved_bidi_defects = None
            all_cleared = False
            verified_status = False

        return {
            "strategy": self.strategy,
            "verified": verified_status,
            "source_patch_verified": source_patch_verified,
            "git_patch": git_patch_text,
            "initial_overflows": initial_overflows,
            "initial_collisions": initial_collisions,
            "initial_bidi_defects": initial_bidi_defects,
            "final_overflows": final_overflows,
            "final_collisions": final_collisions,
            "final_bidi_defects": final_bidi_defects,
            "resolved_overflows": resolved_overflows,
            "resolved_collisions": resolved_collisions,
            "resolved_bidi_defects": resolved_bidi_defects,
            "diagnosed_issues": diagnosed_issues,
            "initial_diagnosed_issues": initial_diagnosed_issues,
            "dynamic_css": applied_css,
            "chosen_variants": chosen_variants,
            "active_texts": active_texts,
            "all_cleared": all_cleared
        }
