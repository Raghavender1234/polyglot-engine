"""
Polyglot CLI — Automated Localization Layout Scanner & Verified Repair Engine
Commands:
  polyglot scan <url> [--locales ...] [--viewports ...] [--output ...] [--json ...]
  polyglot diagnose <report.json>
  polyglot repair <url> [--locales ...] [--viewports ...] [--strategy auto|css-only|text-only] [--verify] [--repo-path ...]
"""

import os
import sys
import json
import argparse
from typing import Dict, Any, List

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


def cmd_scan(args):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("❌ Error: Playwright is not installed. Please run: pip install playwright && playwright install chromium")
        sys.exit(1)

    url = args.url
    locales = [loc.strip() for loc in args.locales.split(",") if loc.strip()]
    viewports = [vp.strip().lower() for vp in args.viewports.split(",") if vp.strip()]
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

    url = args.url
    locales = [loc.strip() for loc in args.locales.split(",") if loc.strip()]
    viewports = [vp.strip().lower() for vp in args.viewports.split(",") if vp.strip()]
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
                        verify=verify
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

                    # Capture post-repair screenshot
                    post_screenshot = os.path.join(output_dir, f"polyglot_repair_after_{locale}_{vp_name}.png")
                    page.screenshot(path=post_screenshot, full_page=True)

                    # 4. Genuine Git Diff Patching if repo_path provided
                    git_patch_text = None
                    if repo_path and (repair_results.get("dynamic_css") or repair_results.get("initial_diagnosed_issues")):
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


def main():
    parser = argparse.ArgumentParser(
        prog="polyglot",
        description="Polyglot Engine — Automated Layout Scanner, Diagnoser & Closed-Loop Repair CLI"
    )
    subparsers = parser.add_subparsers(dest="command", required=True, help="Available subcommands")

    # Command: scan
    scan_parser = subparsers.add_parser("scan", help="Scan a target webpage for multilingual layout breakage")
    scan_parser.add_argument("url", help="Target URL to inspect (e.g. https://play.grafana.org/alerting/list)")
    scan_parser.add_argument("--locales", default="de-DE", help="Comma-separated target locales (e.g. de-DE,ar-SA)")
    scan_parser.add_argument("--viewports", default="desktop", help="Comma-separated viewports: desktop, mobile, tablet")
    scan_parser.add_argument("--output", default="polyglot_audit_report.html", help="Path to write HTML report")
    scan_parser.add_argument("--json", default=None, help="Path to write JSON report")
    scan_parser.add_argument("--bypass-presets", action="store_true", help="Bypass preset translations and query OpenAI API directly")
    scan_parser.add_argument("--max-elements", type=int, default=0, help="Maximum interactive elements to inspect (default: 0 = unlimited whole-page scan)")
    scan_parser.add_argument("--no-headless", action="store_true", help="Run browser in headful mode")
    scan_parser.set_defaults(func=cmd_scan)

    # Command: diagnose
    diag_parser = subparsers.add_parser("diagnose", help="Diagnose root causes from an existing JSON audit report")
    diag_parser.add_argument("report_file", help="Path to JSON audit report file")
    diag_parser.set_defaults(func=cmd_diagnose)

    # Command: repair
    rep_parser = subparsers.add_parser("repair", help="Execute closed-loop multi-candidate repair on a webpage")
    rep_parser.add_argument("url", help="Target URL to repair")
    rep_parser.add_argument("--locales", default="de-DE", help="Comma-separated target locales (e.g. de-DE,ar-SA)")
    rep_parser.add_argument("--viewports", default="desktop", help="Comma-separated viewports: desktop, mobile, tablet")
    rep_parser.add_argument("--strategy", default="auto", choices=["auto", "css-only", "text-only"], help="Repair strategy")
    rep_parser.add_argument("--verify", action="store_true", default=True, help="Verify repairs in isolated browser")
    rep_parser.add_argument("--no-verify", action="store_false", dest="verify", help="Disable post-repair verification check")
    rep_parser.add_argument("--repo-path", default=None, help="Path to local source repository for Git diff patching")
    rep_parser.add_argument("--output", default="polyglot_repair_report.html", help="Path to write HTML report")
    rep_parser.add_argument("--json", default=None, help="Path to write JSON report")
    rep_parser.add_argument("--bypass-presets", action="store_true", help="Bypass preset translations and query OpenAI API directly")
    rep_parser.add_argument("--max-elements", type=int, default=0, help="Maximum interactive elements to repair (default: 0 = unlimited whole-page repair)")
    rep_parser.add_argument("--no-headless", action="store_true", help="Run browser in headful mode")
    rep_parser.set_defaults(func=cmd_repair)

    parsed = parser.parse_args()
    parsed.func(parsed)


if __name__ == "__main__":
    main()
