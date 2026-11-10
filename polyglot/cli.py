"""
Polyglot CLI — Automated Localization Layout Scanner & Verified Repair Engine
Commands:
  polyglot init [--url ...] [--locales ...] [--config ...]
  polyglot scan [url] [--locales ...] [--viewports ...] [--output ...] [--fail-on ...]
  polyglot report [report.html] [--no-open]
  polyglot fix [url] [--strategy auto|css-only|text-only] [--repo-path ...]
  polyglot repair [url] (alias for fix)
  polyglot verify [url] [--locales ...] [--viewports ...]
  polyglot diagnose <report.json>
"""


import os
import sys
import json
import argparse
import webbrowser
from typing import Dict, Any, List, Optional

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from .scanner import DOMScanner
from .detector import CollisionDetector
from .diagnosis import RootCauseDiagnoser
from .patcher import DynamicCSSPatcher, GitDiffPatcher
from .repair import RepairOrchestrator, JS_APPLY_BATCH_TEXT
from .reporting import HTMLReportGenerator

# Import translation engine from app
try:
    from app.engines.llm_translator import llm_engine
except ImportError:
    # If invoked directly or installed as standalone
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    from app.engines.llm_translator import llm_engine


VIEWPORT_PRESETS = {
    "desktop": {"width": 1280, "height": 800},
    "mobile": {"width": 390, "height": 844},
    "tablet": {"width": 768, "height": 1024}
}


def load_project_config(config_path: str = "polyglot.config.json") -> Dict[str, Any]:
    """Loads project configuration from polyglot.config.json if present."""
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def format_verify_scorecard(target_url: str, ver_data: Dict[str, Any]) -> str:
    """Renders an ASCII scorecard for Layer 6 Cross-Locale Regression Verification."""
    lines = []
    lines.append("")
    lines.append("=" * 86)
    lines.append(f"  POLYGLOT CROSS-LOCALE REGRESSION VERIFICATION: {target_url}")
    lines.append("=" * 86)
    lines.append(f" {'Locale':<10} | {'Viewport':<16} | {'Overflows':<10} | {'Collisions':<11} | {'BiDi Errors':<12} | {'Status':<10}")
    lines.append("-" * 86)

    matrix = ver_data.get("matrix_results", {})
    for key, res in matrix.items():
        loc = res.get("locale", "unknown")
        vp = res.get("viewport", "desktop")
        ov = res.get("overflows", 0)
        col = res.get("collisions", 0)
        bidi = res.get("bidi", 0)
        clean = res.get("is_clean", False)
        status = "CLEAN ✅" if clean else "REGRESSED ❌"
        lines.append(f" {loc:<10} | {vp:<16} | {ov:<10} | {col:<11} | {bidi:<12} | {status:<10}")

    lines.append("-" * 86)
    tot_runs = ver_data.get("total_matrix_runs", 0)
    reg_cnt = ver_data.get("regressions_introduced", 0)
    reg_rate = ver_data.get("regression_rate_pct", 0.0)
    all_clean = ver_data.get("all_locales_clean", False)
    overall = "CLEAN ✅" if all_clean else "REGRESSED ❌"
    lines.append(f" {'SUMMARY':<10} | {f'{tot_runs} matrix runs':<16} | {'Regressions: ' + str(reg_cnt):<23} | {'Rate: ' + str(reg_rate) + '%':<12} | {overall:<10}")
    lines.append("=" * 86)
    lines.append("")
    return "\n".join(lines)



def format_scan_scorecard(target_url: str, all_runs: List[Dict[str, Any]]) -> str:
    """Renders a structured, aligned ASCII scorecard summarizing audit results."""
    lines = []
    lines.append("")
    lines.append("=" * 86)
    lines.append(f"  POLYGLOT MULTILINGUAL AUDIT SCORECARD: {target_url}")
    lines.append("=" * 86)
    lines.append(f" {'Locale':<10} | {'Viewport':<18} | {'Overflows':<10} | {'Collisions':<11} | {'BiDi Errors':<12} | {'Status':<10}")
    lines.append("-" * 86)

    total_overflows = 0
    total_collisions = 0
    total_bidi = 0

    for run in all_runs:
        locale = run.get("locale", "unknown")
        vp = run.get("viewport", "desktop")
        ov = run.get("initial_overflows", 0)
        col = run.get("initial_collisions", 0)
        bidi = run.get("initial_bidi_defects", 0)
        total_overflows += ov
        total_collisions += col
        total_bidi += bidi

        run_issues = ov + col + bidi
        status_str = "FAILED ❌" if run_issues > 0 else "PASSED ✅"
        lines.append(f" {locale:<10} | {vp:<18} | {ov:<10} | {col:<11} | {bidi:<12} | {status_str:<10}")

    lines.append("-" * 86)
    overall_defects = total_overflows + total_collisions + total_bidi
    overall_status = "FAILED ❌" if overall_defects > 0 else "PASSED ✅"
    lines.append(f" {'TOTAL':<10} | {f'{len(all_runs)} run(s)':<18} | {total_overflows:<10} | {total_collisions:<11} | {total_bidi:<12} | {overall_status:<10}")
    lines.append("=" * 86)

    if overall_defects > 0:
        lines.append(f"⚠️  Found {overall_defects} layout defect(s) across {len(all_runs)} test run(s).")
        lines.append(f"👉 Run 'polyglot report' to open interactive visual report.")
        lines.append(f"👉 Run 'polyglot fix {target_url}' to generate verified source-code repairs.")
    else:
        lines.append("🎉 All evaluated components passed layout and BiDi verification with zero defects!")
        lines.append(f"👉 Run 'polyglot report' to inspect the clean verification audit.")
    lines.append("")
    return "\n".join(lines)


def format_repair_scorecard(target_url: str, all_repair_runs: List[Dict[str, Any]]) -> str:
    """Renders a structured ASCII scorecard for closed-loop repair verification."""
    lines = []
    lines.append("")
    lines.append("=" * 90)
    lines.append(f"  POLYGLOT CLOSED-LOOP REPAIR SCORECARD: {target_url}")
    lines.append("=" * 90)
    lines.append(f" {'Locale':<10} | {'Viewport':<18} | {'Initial':<8} | {'Resolved':<9} | {'Remaining':<10} | {'Verified':<9} | {'Status':<10}")
    lines.append("-" * 90)

    total_init = 0
    total_res = 0
    total_rem = 0

    for run in all_repair_runs:
        locale = run.get("locale", "unknown")
        vp = run.get("viewport", "desktop")
        ov_i = run.get("initial_overflows", 0)
        col_i = run.get("initial_collisions", 0)
        bidi_i = run.get("initial_bidi_defects", 0)
        init_cnt = ov_i + col_i + bidi_i

        ov_r = run.get("resolved_overflows", 0)
        col_r = run.get("resolved_collisions", 0)
        bidi_r = run.get("resolved_bidi_defects", 0)
        res_cnt = ov_r + col_r + bidi_r

        ov_f = run.get("final_overflows", 0)
        col_f = run.get("final_collisions", 0)
        bidi_f = run.get("final_bidi_defects", 0)
        rem_cnt = ov_f + col_f + bidi_f

        total_init += init_cnt
        total_res += res_cnt
        total_rem += rem_cnt

        verified = "YES" if run.get("verified", True) else "NO"
        status_str = "REPAIRED ✅" if rem_cnt == 0 else "PARTIAL ⚠️"
        lines.append(f" {locale:<10} | {vp:<18} | {init_cnt:<8} | {res_cnt:<9} | {rem_cnt:<10} | {verified:<9} | {status_str:<10}")

    lines.append("-" * 90)
    overall_status = "REPAIRED ✅" if total_rem == 0 else "PARTIAL ⚠️"
    lines.append(f" {'TOTAL':<10} | {f'{len(all_repair_runs)} run(s)':<18} | {total_init:<8} | {total_res:<9} | {total_rem:<10} | {'--':<9} | {overall_status:<10}")
    lines.append("=" * 90)

    if total_rem == 0:
        lines.append("🎉 All multilingual layout defects successfully repaired and verified in browser!")
        lines.append("👉 Run 'polyglot report' to inspect the verified before/after diffs.")
    else:
        lines.append(f"⚠️  {total_rem} defect(s) remain unverified. Check 'polyglot report' for details.")
    lines.append("")
    return "\n".join(lines)


def format_markdown_summary(target_url: str, all_runs: List[Dict[str, Any]], is_repair: bool = False) -> str:
    """Generates a GitHub Flavored Markdown summary table for PR comments and CI Step Summaries."""
    lines = []
    lines.append(f"## 🌐 Polyglot Multilingual Audit Summary: `{target_url}`")
    lines.append("")
    if is_repair:
        lines.append("| Locale | Viewport | Initial Defects | Resolved | Remaining | Verified | Status |")
        lines.append("|:-------|:---------|:---------------:|:--------:|:---------:|:--------:|:------:|")
        for r in all_runs:
            loc = r.get("locale", "unknown")
            vp = r.get("viewport", "desktop")
            init_c = r.get("initial_overflows", 0) + r.get("initial_collisions", 0) + r.get("initial_bidi_defects", 0)
            res_c = r.get("resolved_overflows", 0) + r.get("resolved_collisions", 0) + r.get("resolved_bidi_defects", 0)
            rem_c = r.get("final_overflows", 0) + r.get("final_collisions", 0) + r.get("final_bidi_defects", 0)
            ver = "✅ Yes" if r.get("verified", True) else "❌ No"
            st = "✅ Repaired" if rem_c == 0 else "⚠️ Partial"
            lines.append(f"| `{loc}` | {vp} | {init_c} | {res_c} | {rem_c} | {ver} | {st} |")
    else:
        lines.append("| Locale | Viewport | Overflows | Collisions | BiDi Inversions | Status |")
        lines.append("|:-------|:---------|:---------:|:----------:|:---------------:|:------:|")
        for r in all_runs:
            loc = r.get("locale", "unknown")
            vp = r.get("viewport", "desktop")
            ov = r.get("initial_overflows", 0)
            col = r.get("initial_collisions", 0)
            bidi = r.get("initial_bidi_defects", 0)
            tot = ov + col + bidi
            st = "❌ Failed" if tot > 0 else "✅ Passed"
            lines.append(f"| `{loc}` | {vp} | {ov} | {col} | {bidi} | {st} |")

    lines.append("")
    all_issues = []
    for r in all_runs:
        for iss in r.get("diagnosed_issues", []):
            all_issues.append((r.get("locale"), iss))

    if all_issues:
        lines.append(f"<details><summary><b>🔍 Detected Layout Defects & Suggested Remedies ({len(all_issues)})</b></summary>")
        lines.append("")
        for loc, iss in all_issues[:15]:
            cat = iss.get("category", "DEFECT")
            sel = iss.get("selector", "element")
            rem = iss.get("remedy", "")
            lines.append(f"- **`{loc}` [{cat}]** on `{sel}`")
            if rem:
                lines.append(f"  - *Remedy:* {rem}")
        if len(all_issues) > 15:
            lines.append(f"- *...and {len(all_issues) - 15} more defects (view full HTML report).*")
        lines.append("")
        lines.append("</details>")
        lines.append("")

    return "\n".join(lines)


def write_ci_summary(content: str, summary_file: Optional[str] = None):
    """Writes the markdown summary to the specified file or $GITHUB_STEP_SUMMARY if available."""
    target_path = summary_file or os.getenv("GITHUB_STEP_SUMMARY")
    if target_path:
        try:
            with open(target_path, "a" if not summary_file else "w", encoding="utf-8") as f:
                f.write("\n" + content + "\n")
            print(f"📝 GitHub Step Summary recorded to: {target_path}")
        except Exception as e:
            print(f"⚠️ Failed to write Step Summary to {target_path}: {e}")



def evaluate_exit_code(all_runs: List[Dict[str, Any]], fail_on: str = "any", is_repair: bool = False) -> int:
    """Calculates CI exit code based on the --fail-on policy.
    Returns 0 if thresholds pass, 1 if failures exceed policy.
    """
    if fail_on == "none":
        return 0

    if is_repair:
        # For repair runs, evaluate remaining/final defects
        rem_defects = sum(
            r.get("final_overflows", 0) + r.get("final_collisions", 0) + r.get("final_bidi_defects", 0)
            for r in all_runs
        )
        if not all(r.get("verified", True) for r in all_runs):
            return 1
        return 1 if rem_defects > 0 else 0
    else:
        # For scan runs, evaluate initial defects found
        total_defects = sum(
            r.get("initial_overflows", 0) + r.get("initial_collisions", 0) + r.get("initial_bidi_defects", 0)
            for r in all_runs
        )
        if fail_on == "critical":
            crit_defects = sum(
                r.get("initial_overflows", 0) + r.get("initial_bidi_defects", 0)
                for r in all_runs
            )
            return 1 if crit_defects > 0 else 0
        return 1 if total_defects > 0 else 0



def cmd_scan(args):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("❌ Error: Playwright is not installed. Please run: pip install playwright && playwright install chromium")
        sys.exit(1)

    proj_cfg = load_project_config()
    url = args.url or proj_cfg.get("url")
    if not url:
        print("❌ Error: No target URL specified. Provide a URL argument or run 'polyglot init' to create polyglot.config.json.")
        sys.exit(1)

    cfg_locales = ",".join(proj_cfg.get("locales", [])) if isinstance(proj_cfg.get("locales"), list) else proj_cfg.get("locales")
    cfg_viewports = ",".join(proj_cfg.get("viewports", [])) if isinstance(proj_cfg.get("viewports"), list) else proj_cfg.get("viewports")
    raw_locales = args.locales if args.locales != "de-DE" or not cfg_locales else cfg_locales
    raw_viewports = args.viewports if args.viewports != "desktop" or not cfg_viewports else cfg_viewports

    locales = [loc.strip() for loc in raw_locales.split(",") if loc.strip()]
    viewports = [vp.strip().lower() for vp in raw_viewports.split(",") if vp.strip()]
    bypass_presets = args.bypass_presets
    max_elements = args.max_elements
    headless = not args.no_headless


    print(f"🚀 Polyglot Scan initiated for: {url}")
    print(f"🌍 Locales: {', '.join(locales)} | Viewports: {', '.join(viewports)}")

    all_runs = []
    output_dir = os.path.dirname(os.path.abspath(args.output)) or "."

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=headless)
        except Exception as e:
            print(f"❌ Failed to launch Chromium: {e}. Run 'playwright install chromium' to install browsers.")
            sys.exit(1)

        try:
            for locale in locales:
                for vp_name in viewports:
                    vp = VIEWPORT_PRESETS.get(vp_name, VIEWPORT_PRESETS["desktop"])
                    context = browser.new_context(
                        viewport=vp,
                        locale=locale,
                        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
                    )
                    page = context.new_page()

                    print(f"\n📡 Navigating to {url} ({locale} @ {vp_name} {vp['width']}x{vp['height']})...")
                    try:
                        page.goto(url, wait_until="networkidle", timeout=30000)
                    except Exception as e:
                        print(f"⚠️ Page load warning: {e}. Attempting DOM discovery anyway.")

                    try:
                        page.wait_for_selector('button, a, nav, h1, h2, h3, [role="button"]', timeout=8000)
                    except Exception:
                        pass

                    page.wait_for_timeout(1000)

                    # 1. Discover Elements
                    raw_elements, stats = DOMScanner.discover_with_stats(page)
                    target_elements = raw_elements[:max_elements] if (max_elements and max_elements > 0) else raw_elements
                    skipped_count = max(0, len(raw_elements) - len(target_elements))
                    print(f"🔍 Discovered {len(raw_elements)} UI candidates across {stats['totalDomElements']} DOM nodes ({stats['excludedByDesign']} non-text/hidden excluded by design). Evaluated: {len(target_elements)} | Skipped: {skipped_count}")

                    # 2. Fetch Translations with Provenance
                    provenance_counts = {"OPENAI_API": 0, "PRESET": 0, "PSEUDO": 0, "FALLBACK": 0}
                    translations_payload = []
                    target_ids = []

                    is_rtl = locale.lower().startswith(("ar", "ur", "he", "fa"))

                    print(f"🤖 Generating translations for {locale} (Bypass presets: {bypass_presets})...")
                    for el in target_elements:
                        orig_text = el["text"]
                        target_ids.append(el["id"])

                        variants, source = llm_engine.translate_with_variants(
                            source_text=orig_text,
                            source_locale="en-US",
                            target_locale=locale,
                            bypass_presets=bypass_presets
                        )
                        provenance_counts[source] = provenance_counts.get(source, 0) + 1

                        translations_payload.append({
                            "id": el["id"],
                            "text": variants.standard,
                            "dir": "rtl" if is_rtl else "ltr"
                        })

                    # 3. Apply standard translations
                    page.evaluate(JS_APPLY_BATCH_TEXT, translations_payload)
                    page.wait_for_timeout(500)

                    # 4. Detect Overflows, Full-Page Collisions & BiDi Defects
                    detection = CollisionDetector.detect(page, target_ids)
                    overflow_count = detection["overflowCount"]
                    collision_count = detection["collisionCount"]
                    bidi_count = detection.get("bidiCount", 0)

                    print(f"📊 Audit Results for {locale} ({vp_name}):")
                    print(f"   - Container Overflows: {overflow_count}")
                    print(f"   - Full-Page Collisions: {collision_count}")
                    print(f"   - BiDi Directional / Isolation Defects: {bidi_count}")
                    print(f"   - Provenance: {provenance_counts}")

                    # 5. Diagnose Root Causes
                    diagnosed_issues = []
                    el_map = {el["id"]: el for el in target_elements}

                    for ovf in detection["overflows"]:
                        el = el_map.get(ovf["id"], {})
                        merged_el = {**el, **ovf}
                        diag = RootCauseDiagnoser.diagnose_overflow(merged_el, ovf["overflowPx"], locale)
                        diag["id"] = ovf["id"]
                        diag["selector"] = ovf["selector"]
                        diag["text"] = ovf["text"]
                        diag["overflow_px"] = ovf["overflowPx"]
                        diagnosed_issues.append(diag)

                    for col in detection["collisions"]:
                        el = el_map.get(col["translatedId"], {})
                        merged_el = {**el, **col}
                        diag = RootCauseDiagnoser.diagnose_collision(col, merged_el, {})
                        diag["id"] = col["translatedId"]
                        diag["selector"] = col["selector1"]
                        diag["collided_with"] = col["selector2"]
                        diag["overlap_px"] = col["overlapX"]
                        diagnosed_issues.append(diag)

                    for bidi in detection.get("bidiIssues", []):
                        diag = {
                            "id": bidi.get("id"),
                            "selector": bidi.get("selector"),
                            "category": "BIDI_DIRECTIONAL_ISOLATION",
                            "explanation": bidi.get("explanation"),
                            "remedy": bidi.get("remedy"),
                            "text": bidi.get("text"),
                            "overflow_px": 0.0
                        }
                        diagnosed_issues.append(diag)

                    # 6. Capture Evidence Screenshot
                    screenshot_name = f"polyglot_scan_{locale}_{vp_name}.png"
                    screenshot_path = os.path.join(output_dir, screenshot_name)
                    page.screenshot(path=screenshot_path, full_page=True)

                    # 7. Compile Run Data
                    run_data = {
                        "target_url": url,
                        "locale": locale,
                        "viewport": f"{vp_name} ({vp['width']}x{vp['height']})",
                        "total_scanned": len(raw_elements),
                        "total_evaluated": len(target_elements),
                        "total_skipped": skipped_count,
                        "total_dom_elements": stats.get("totalDomElements", len(raw_elements)),
                        "excluded_by_design": stats.get("excludedByDesign", 0),
                        "provenance_counts": provenance_counts,
                        "initial_overflows": overflow_count,
                        "initial_collisions": collision_count,
                        "initial_bidi_defects": bidi_count,
                        "final_overflows": overflow_count,
                        "final_collisions": collision_count,
                        "final_bidi_defects": bidi_count,
                        "resolved_overflows": 0,
                        "resolved_collisions": 0,
                        "resolved_bidi_defects": 0,
                        "diagnosed_issues": diagnosed_issues,
                        "screenshots": {f"Scan {locale} ({vp_name})": screenshot_path}
                    }
                    all_runs.append(run_data)
                    context.close()
        finally:
            browser.close()

    # Write Master Report (never overwritten)
    if len(all_runs) == 1:
        HTMLReportGenerator.generate(all_runs[0], args.output)
        if args.json:
            with open(args.json, "w", encoding="utf-8") as jf:
                json.dump(all_runs[0], jf, indent=2, ensure_ascii=False)
            print(f"📋 Structured JSON report saved to: {args.json}")
    else:
        master_report = {
            "target_url": url,
            "total_runs": len(all_runs),
            "runs": all_runs
        }
        HTMLReportGenerator.generate(master_report, args.output)
        if args.json:
            with open(args.json, "w", encoding="utf-8") as jf:
                json.dump(master_report, jf, indent=2, ensure_ascii=False)
            print(f"📋 Multi-Run Matrix JSON report saved to: {args.json}")

    # Print Terminal Scorecard
    print(format_scan_scorecard(url, all_runs))

    # Write CI Markdown Summary (e.g. to $GITHUB_STEP_SUMMARY)
    md_summary = format_markdown_summary(url, all_runs, is_repair=False)
    write_ci_summary(md_summary, summary_file=getattr(args, "markdown_summary", None))

    # Evaluate CI exit code
    exit_code = evaluate_exit_code(all_runs, fail_on=getattr(args, "fail_on", "any"), is_repair=False)
    if exit_code != 0:
        print(f"🛑 Polyglot audit exited with code {exit_code} (defects detected with --fail-on={getattr(args, 'fail_on', 'any')}).")
        sys.exit(exit_code)


def cmd_diagnose(args):
    report_file = args.report_file
    if not os.path.exists(report_file):
        print(f"❌ Error: Report file '{report_file}' not found.")
        sys.exit(1)

    with open(report_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    runs = data.get("runs", [data])

    print("=" * 70)
    print(f"🔬 Polyglot Diagnostic Breakdown for: {data.get('target_url', 'Report')}")
    print(f"📊 Total Evaluation Runs: {len(runs)}")
    print("=" * 70)

    for run in runs:
        locale = run.get("locale", "Unknown")
        vp = run.get("viewport", "Unknown")
        diagnosed = run.get("diagnosed_issues", [])

        print(f"\n🌍 Locale: {locale} | Viewport: {vp} | Issues Diagnosed: {len(diagnosed)}")
        print("-" * 70)

        if not diagnosed:
            print("  ✅ No layout constraints or collisions diagnosed for this run.")
            continue

        for i, issue in enumerate(diagnosed, 1):
            cat = issue.get("category", "UNKNOWN")
            sel = issue.get("selector", "Unknown selector")
            expl = issue.get("explanation", "")
            rem = issue.get("remedy", "")
            ovf = issue.get("overflow_px", 0)

            print(f"  [{i}] Category: {cat}")
            print(f"      Selector:    {sel}")
            print(f"      Overflow:    +{ovf:.1f}px")
            print(f"      Root Cause:  {expl}")
            print(f"      Remedy:      {rem}")

    print("\n" + "=" * 70)


def cmd_repair(args):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("❌ Error: Playwright is not installed. Please run: pip install playwright && playwright install chromium")
        sys.exit(1)

    proj_cfg = load_project_config()
    url = args.url or proj_cfg.get("url")
    if not url:
        print("❌ Error: No target URL specified. Provide a URL argument or run 'polyglot init' to create polyglot.config.json.")
        sys.exit(1)

    cfg_locales = ",".join(proj_cfg.get("locales", [])) if isinstance(proj_cfg.get("locales"), list) else proj_cfg.get("locales")
    cfg_viewports = ",".join(proj_cfg.get("viewports", [])) if isinstance(proj_cfg.get("viewports"), list) else proj_cfg.get("viewports")
    raw_locales = args.locales if args.locales != "de-DE" or not cfg_locales else cfg_locales
    raw_viewports = args.viewports if args.viewports != "desktop" or not cfg_viewports else cfg_viewports

    locales = [loc.strip() for loc in raw_locales.split(",") if loc.strip()]
    viewports = [vp.strip().lower() for vp in raw_viewports.split(",") if vp.strip()]
    strategy = args.strategy
    repo_path = args.repo_path
    bypass_presets = args.bypass_presets
    max_elements = args.max_elements
    verify = args.verify
    headless = not args.no_headless


    print(f"🛠️  Polyglot Closed-Loop Repair initiated for: {url}")
    print(f"🌍 Locales: {', '.join(locales)} | Viewports: {', '.join(viewports)} | Strategy: {strategy} | Verify: {verify}")
    if repo_path:
        print(f"📂 Source Repository: {repo_path}")

    all_repair_runs = []
    output_dir = os.path.dirname(os.path.abspath(args.output)) or "."

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=headless)
        except Exception as e:
            print(f"❌ Failed to launch Chromium: {e}. Run 'playwright install chromium' to install browsers.")
            sys.exit(1)

        try:
            for locale in locales:
                for vp_name in viewports:
                    vp = VIEWPORT_PRESETS.get(vp_name, VIEWPORT_PRESETS["desktop"])
                    context = browser.new_context(viewport=vp, locale=locale)
                    page = context.new_page()

                    print(f"\n📡 Navigating to {url} ({locale} @ {vp_name})...")
                    try:
                        page.goto(url, wait_until="networkidle", timeout=30000)
                    except Exception as e:
                        print(f"⚠️ Page load warning: {e}. Proceeding.")

                    try:
                        page.wait_for_selector('button, a, nav, h1, h2, h3, [role="button"]', timeout=8000)
                    except Exception:
                        pass

                    page.wait_for_timeout(1000)

                    # 1. Discover Elements
                    raw_elements, stats = DOMScanner.discover_with_stats(page)
                    target_elements = raw_elements[:max_elements] if (max_elements and max_elements > 0) else raw_elements
                    skipped_count = max(0, len(raw_elements) - len(target_elements))
                    print(f"🔍 Discovered {len(raw_elements)} elements across {stats['totalDomElements']} DOM nodes ({stats['excludedByDesign']} excluded by design). Repairing {len(target_elements)} targets (Skipped: {skipped_count}).")

                    # Capture initial baseline screenshot
                    orig_screenshot = os.path.join(output_dir, f"polyglot_repair_before_{locale}_{vp_name}.png")
                    page.screenshot(path=orig_screenshot, full_page=True)

                    # 2. Fetch Multi-Length Translation Candidates
                    candidates_map = {}
                    provenance_counts = {"OPENAI_API": 0, "PRESET": 0, "PSEUDO": 0, "FALLBACK": 0}
                    is_rtl = locale.lower().startswith(("ar", "ur", "he", "fa"))

                    print(f"🤖 Fetching multi-candidate translations for {locale}...")
                    for el in target_elements:
                        variants, source = llm_engine.translate_with_variants(
                            source_text=el["text"],
                            source_locale="en-US",
                            target_locale=locale,
                            bypass_presets=bypass_presets
                        )
                        provenance_counts[source] = provenance_counts.get(source, 0) + 1

                        candidates_map[el["id"]] = {
                            "standard": variants.standard,
                            "compact": variants.compact,
                            "ultra_short": variants.ultra_short,
                            "dir": "rtl" if is_rtl else "ltr"
                        }

                    # 3. Execute Closed-Loop Repair Orchestrator with strategy & verify controls
                    orchestrator = RepairOrchestrator(
                        page=page,
                        target_elements=target_elements,
                        candidates_map=candidates_map,
                        locale=locale,
                        strategy=strategy,
                        verify=verify,
                        repo_path=repo_path
                    )
                    repair_results = orchestrator.execute_closed_loop_repair()

                    print(f"\n🏁 Closed-Loop Repair Finished for {locale} ({vp_name}):")
                    print(f"   - Initial Overflows:   {repair_results['initial_overflows']}")
                    print(f"   - Initial Collisions:  {repair_results['initial_collisions']}")
                    print(f"   - Initial BiDi Flaws:  {repair_results.get('initial_bidi_defects', 0)}")
                    print(f"   - Final Overflows:     {repair_results['final_overflows']}")
                    print(f"   - Final Collisions:    {repair_results['final_collisions']}")
                    print(f"   - Final BiDi Flaws:    {repair_results.get('final_bidi_defects', 0)}")
                    print(f"   - Overflows Cleared:   {repair_results['resolved_overflows']}")
                    print(f"   - Collisions Cleared:  {repair_results['resolved_collisions']}")
                    print(f"   - BiDi Cleared:        {repair_results.get('resolved_bidi_defects', 0)}")
                    if repair_results.get("source_patch_verified"):
                        print(f"   - Source Patch Reload: ✅ 100% Verified in clean browser reload!")

                    # Capture post-repair screenshot
                    post_screenshot = os.path.join(output_dir, f"polyglot_repair_after_{locale}_{vp_name}.png")
                    page.screenshot(path=post_screenshot, full_page=True)

                    # 4. Write Git Diff Patch if generated and repo_path provided
                    git_patch_text = repair_results.get("git_patch")
                    if repo_path and not git_patch_text:
                        all_diagnosed = repair_results.get("diagnosed_issues") or repair_results.get("initial_diagnosed_issues", [])
                        git_patch_text = GitDiffPatcher.generate_patch(repo_path, all_diagnosed)

                    if git_patch_text:
                        patch_path = os.path.join(output_dir, f"polyglot_repair_{locale}_{vp_name}.patch")
                        with open(patch_path, "w", encoding="utf-8") as pf:
                            pf.write(git_patch_text)
                        print(f"📝 Genuine Git diff patch written to: {patch_path}")

                    # 5. Compile Run Data
                    run_data = {
                        "target_url": url,
                        "locale": locale,
                        "viewport": f"{vp_name} ({vp['width']}x{vp['height']})",
                        "strategy": strategy,
                        "verified": repair_results.get("verified", True),
                        "total_scanned": len(raw_elements),
                        "total_evaluated": len(target_elements),
                        "total_skipped": skipped_count,
                        "total_dom_elements": stats.get("totalDomElements", len(raw_elements)),
                        "excluded_by_design": stats.get("excludedByDesign", 0),
                        "provenance_counts": provenance_counts,
                        "initial_overflows": repair_results["initial_overflows"],
                        "initial_collisions": repair_results["initial_collisions"],
                        "initial_bidi_defects": repair_results.get("initial_bidi_defects", 0),
                        "final_overflows": repair_results["final_overflows"],
                        "final_collisions": repair_results["final_collisions"],
                        "final_bidi_defects": repair_results.get("final_bidi_defects", 0),
                        "resolved_overflows": repair_results["resolved_overflows"],
                        "resolved_collisions": repair_results["resolved_collisions"],
                        "resolved_bidi_defects": repair_results.get("resolved_bidi_defects", 0),
                        "diagnosed_issues": repair_results["diagnosed_issues"],
                        "dynamic_css": repair_results.get("dynamic_css", ""),
                        "git_patch": git_patch_text,
                        "screenshots": {
                            "Before Repair": orig_screenshot,
                            "After Closed-Loop Repair": post_screenshot
                        }
                    }
                    all_repair_runs.append(run_data)
                    context.close()
        finally:
            browser.close()

    # Write Master Repair Report
    if len(all_repair_runs) == 1:
        HTMLReportGenerator.generate(all_repair_runs[0], args.output)
        if args.json:
            with open(args.json, "w", encoding="utf-8") as jf:
                json.dump(all_repair_runs[0], jf, indent=2, ensure_ascii=False)
            print(f"📋 Structured JSON report saved to: {args.json}")
    else:
        master_report = {
            "target_url": url,
            "strategy": strategy,
            "total_runs": len(all_repair_runs),
            "runs": all_repair_runs
        }
        HTMLReportGenerator.generate(master_report, args.output)
        if args.json:
            with open(args.json, "w", encoding="utf-8") as jf:
                json.dump(master_report, jf, indent=2, ensure_ascii=False)
            print(f"📋 Multi-Run Matrix JSON report saved to: {args.json}")

    # Print Terminal Scorecard
    print(format_repair_scorecard(url, all_repair_runs))

    # Write CI Markdown Summary (e.g. to $GITHUB_STEP_SUMMARY)
    md_summary = format_markdown_summary(url, all_repair_runs, is_repair=True)
    write_ci_summary(md_summary, summary_file=getattr(args, "markdown_summary", None))

    # Evaluate CI exit code
    exit_code = evaluate_exit_code(all_repair_runs, fail_on=getattr(args, "fail_on", "any"), is_repair=True)
    if exit_code != 0:
        print(f"🛑 Polyglot repair exited with code {exit_code} (unresolved defects detected with --fail-on={getattr(args, 'fail_on', 'any')}).")
        sys.exit(exit_code)


def cmd_init(args):
    """Creates a polyglot.config.json in the current directory for zero-friction CLI usage."""
    config_file = args.config
    locales = [loc.strip() for loc in args.locales.split(",") if loc.strip()]
    viewports = [vp.strip().lower() for vp in args.viewports.split(",") if vp.strip()]
    default_cfg = {
        "url": args.url,
        "locales": locales,
        "viewports": viewports,
        "strategy": "auto",
        "fail_on": "any",
        "output_report": "polyglot_audit_report.html"
    }
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(default_cfg, f, indent=2, ensure_ascii=False)

    print("=" * 70)
    print(f"✅ Initialized Polyglot configuration: {os.path.abspath(config_file)}")
    print("=" * 70)
    print(f"🌍 Default Target URL: {args.url}")
    print(f"🗣️  Locales:           {', '.join(locales)}")
    print(f"📱 Viewports:         {', '.join(viewports)}")
    print("\nQuickstart commands:")
    print("  1. polyglot scan             # Audit all configured locales & viewports")
    print("  2. polyglot report           # Open interactive visual HTML report")
    print("  3. polyglot fix              # Generate verified source-code repairs")
    print("  4. polyglot verify           # Run cross-locale regression verification")
    print("=" * 70)


def cmd_verify(args):
    """Executes Layer 6 Cross-Locale Regression Verification across locales & viewports."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("❌ Error: Playwright is not installed. Please run: pip install playwright && playwright install chromium")
        sys.exit(1)

    proj_cfg = load_project_config()
    url = args.url or proj_cfg.get("url")
    if not url:
        print("❌ Error: No target URL specified. Provide a URL argument or run 'polyglot init' to create polyglot.config.json.")
        sys.exit(1)

    cfg_locales = ",".join(proj_cfg.get("locales", [])) if isinstance(proj_cfg.get("locales"), list) else proj_cfg.get("locales")
    cfg_viewports = ",".join(proj_cfg.get("viewports", [])) if isinstance(proj_cfg.get("viewports"), list) else proj_cfg.get("viewports")
    raw_locales = args.locales if args.locales != "en-US,de-DE,ar-SA" or not cfg_locales else cfg_locales
    raw_viewports = args.viewports if args.viewports != "desktop,mobile" or not cfg_viewports else cfg_viewports

    locales = [loc.strip() for loc in raw_locales.split(",") if loc.strip()]
    if "en-US" not in locales:
        locales.insert(0, "en-US")
    vp_names = [vp.strip().lower() for vp in raw_viewports.split(",") if vp.strip()]
    vp_list = [{"name": vn, **VIEWPORT_PRESETS.get(vn, VIEWPORT_PRESETS["desktop"])} for vn in vp_names]
    headless = not args.no_headless

    print(f"🛡️  Polyglot Cross-Locale Regression Verification for: {url}")
    print(f"🌍 Matrix Locales: {', '.join(locales)} | Viewports: {', '.join(vp_names)}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        try:
            page = browser.new_page()
            page.goto(url, wait_until="networkidle", timeout=30000)
            raw_elements, _ = DOMScanner.discover_with_stats(page)
            target_ids = [el["id"] for el in raw_elements]

            locale_payloads = {}
            for loc in locales:
                payload = []
                for el in raw_elements:
                    orig_text = el["text"]
                    if loc.startswith("en"):
                        payload.append({"id": el["id"], "text": orig_text, "dir": "ltr"})
                    else:
                        variants, _ = llm_engine.generate_variants_with_provenance(
                            source_text=orig_text,
                            target_locale=loc,
                            element_type=el.get("tag", "span"),
                            bypass_presets=False
                        )
                        is_rtl = loc.split("-")[0] in ("ar", "he", "fa", "ur")
                        payload.append({
                            "id": el["id"],
                            "text": variants.get("standard", orig_text),
                            "dir": "rtl" if is_rtl else "ltr"
                        })
                locale_payloads[loc] = payload

            ver_results = RepairOrchestrator.verify_cross_locale_regression(
                page=page,
                target_ids=target_ids,
                locale_payloads=locale_payloads,
                viewports=vp_list
            )
        finally:
            browser.close()

    print(format_verify_scorecard(url, ver_results))
    if not ver_results.get("all_locales_clean", False) and getattr(args, "fail_on", "any") != "none":
        print("🛑 Cross-locale verification failed: layout regressions detected.")
        sys.exit(1)


def cmd_report(args):
    """Opens the generated HTML visual report in the default web browser."""
    report_file = args.report_file
    if not report_file:
        for cand in ["polyglot_audit_report.html", "polyglot_repair_report.html"]:
            if os.path.exists(cand):
                report_file = cand
                break

    if not report_file or not os.path.exists(report_file):
        print(f"❌ Error: Report file '{report_file or 'polyglot_audit_report.html'}' not found.")
        print("💡 Run 'polyglot scan <url>' or 'polyglot fix <url>' first to generate an audit report.")
        sys.exit(1)

    abs_path = os.path.abspath(report_file)
    print("=" * 70)
    print("🌐 Polyglot Visual HTML Report")
    print("=" * 70)
    print(f"📁 Path: {abs_path}")
    print(f"🔗 URL:  file:///{abs_path.replace(os.sep, '/')}")
    if not getattr(args, "no_open", False):
        try:
            webbrowser.open(f"file:///{abs_path.replace(os.sep, '/')}")
            print("🚀 Report opened in default browser.")
        except Exception as e:
            print(f"⚠️ Could not launch browser automatically: {e}")
    print("=" * 70)


def _configure_repair_args(subparser):
    """Common arguments shared between 'repair' and 'fix' commands."""
    subparser.add_argument("url", nargs="?", default=None, help="Target URL to repair (or read from polyglot.config.json)")
    subparser.add_argument("--locales", default="de-DE", help="Comma-separated target locales (e.g. de-DE,ar-SA)")
    subparser.add_argument("--viewports", default="desktop", help="Comma-separated viewports: desktop, mobile, tablet")
    subparser.add_argument("--strategy", default="auto", choices=["auto", "css-only", "text-only"], help="Repair strategy")
    subparser.add_argument("--verify", action="store_true", default=True, help="Verify repairs in isolated browser")
    subparser.add_argument("--no-verify", action="store_false", dest="verify", help="Disable post-repair verification check")
    subparser.add_argument("--repo-path", default=None, help="Path to local source repository for Git diff patching")
    subparser.add_argument("--output", default="polyglot_repair_report.html", help="Path to write HTML report")
    subparser.add_argument("--json", default=None, help="Path to write JSON report")
    subparser.add_argument("--markdown-summary", default=None, help="Path to write GitHub Flavored Markdown summary (auto-detects $GITHUB_STEP_SUMMARY)")
    subparser.add_argument("--bypass-presets", action="store_true", help="Bypass preset translations and query OpenAI API directly")
    subparser.add_argument("--max-elements", type=int, default=0, help="Maximum interactive elements to repair (default: 0 = unlimited whole-page repair)")
    subparser.add_argument("--fail-on", choices=["any", "critical", "none"], default="any", help="CI exit code policy: fail on 'any' remaining defect, 'critical' only, or 'none'")
    subparser.add_argument("--no-headless", action="store_true", help="Run browser in headful mode")
    subparser.set_defaults(func=cmd_repair)


def main():
    parser = argparse.ArgumentParser(
        prog="polyglot",
        description="Polyglot Engine — Developer-first CLI that scans, diagnoses and repairs multilingual UI problems directly inside your codebase"
    )
    subparsers = parser.add_subparsers(dest="command", required=True, help="Available subcommands")

    # Command: init
    init_parser = subparsers.add_parser("init", help="Initialize polyglot.config.json in the current directory")
    init_parser.add_argument("--url", default="http://localhost:3000", help="Default target URL")
    init_parser.add_argument("--locales", default="de-DE,ar-SA,ja-JP", help="Default comma-separated locales")
    init_parser.add_argument("--viewports", default="desktop,mobile", help="Default comma-separated viewports")
    init_parser.add_argument("--config", default="polyglot.config.json", help="Path to write configuration file")
    init_parser.set_defaults(func=cmd_init)

    # Command: scan
    scan_parser = subparsers.add_parser("scan", help="Scan a target webpage for multilingual layout breakage")
    scan_parser.add_argument("url", nargs="?", default=None, help="Target URL to inspect (or read from polyglot.config.json)")
    scan_parser.add_argument("--locales", default="de-DE", help="Comma-separated target locales (e.g. de-DE,ar-SA)")
    scan_parser.add_argument("--viewports", default="desktop", help="Comma-separated viewports: desktop, mobile, tablet")
    scan_parser.add_argument("--output", default="polyglot_audit_report.html", help="Path to write HTML report")
    scan_parser.add_argument("--json", default=None, help="Path to write JSON report")
    scan_parser.add_argument("--markdown-summary", default=None, help="Path to write GitHub Flavored Markdown summary (auto-detects $GITHUB_STEP_SUMMARY)")
    scan_parser.add_argument("--bypass-presets", action="store_true", help="Bypass preset translations and query OpenAI API directly")
    scan_parser.add_argument("--max-elements", type=int, default=0, help="Maximum interactive elements to inspect (default: 0 = unlimited whole-page scan)")
    scan_parser.add_argument("--fail-on", choices=["any", "critical", "none"], default="any", help="CI exit code policy: fail on 'any' defect found, 'critical' only, or 'none'")
    scan_parser.add_argument("--no-headless", action="store_true", help="Run browser in headful mode")
    scan_parser.set_defaults(func=cmd_scan)

    # Command: report
    report_parser = subparsers.add_parser("report", help="Open visual HTML report in the default browser")
    report_parser.add_argument("report_file", nargs="?", default=None, help="Path to HTML report (defaults to polyglot_audit_report.html or polyglot_repair_report.html)")
    report_parser.add_argument("--no-open", action="store_true", help="Do not automatically launch browser, just print path and URL")
    report_parser.set_defaults(func=cmd_report)

    # Command: fix (preferred verb)
    fix_parser = subparsers.add_parser("fix", help="Execute closed-loop multi-candidate repair and generate Git diff")
    _configure_repair_args(fix_parser)

    # Command: repair (alias for fix)
    rep_parser = subparsers.add_parser("repair", help="Execute closed-loop multi-candidate repair on a webpage")
    _configure_repair_args(rep_parser)

    # Command: verify
    ver_parser = subparsers.add_parser("verify", help="Run cross-locale & multi-viewport regression verification")
    ver_parser.add_argument("url", nargs="?", default=None, help="Target URL to verify (or read from polyglot.config.json)")
    ver_parser.add_argument("--locales", default="en-US,de-DE,ar-SA", help="Comma-separated locales to verify against regressions")
    ver_parser.add_argument("--viewports", default="desktop,mobile", help="Comma-separated viewports: desktop, mobile, tablet")
    ver_parser.add_argument("--fail-on", choices=["any", "none"], default="any", help="Exit with code 1 if any regression is detected")
    ver_parser.add_argument("--no-headless", action="store_true", help="Run browser in headful mode")
    ver_parser.set_defaults(func=cmd_verify)

    # Command: diagnose
    diag_parser = subparsers.add_parser("diagnose", help="Diagnose root causes from an existing JSON audit report")
    diag_parser.add_argument("report_file", help="Path to JSON audit report file")
    diag_parser.set_defaults(func=cmd_diagnose)

    parsed = parser.parse_args()
    parsed.func(parsed)




if __name__ == "__main__":
    main()
