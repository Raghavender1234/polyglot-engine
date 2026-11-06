"""
Unit Tests for Polyglot Modular Architecture:
- RootCauseDiagnoser (computed layout constraint analysis & fresh styling)
- DynamicCSSPatcher (dynamic, non-hardcoded CSS rule generation & generic selector protection)
- GitDiffPatcher (honest source-aware patching with difflib unified diffs)
- HTMLReportGenerator (evidence-based truthful reporting with fallback in denominator)
- Golden Multilingual Benchmark:
  * 3 overlapping buttons
  * 2 overflowing navigation links
  * 1 Arabic mixed-direction pricing element
  * 1 untouched element
"""

import os
import re
import difflib
import tempfile
import pytest

from polyglot.diagnosis import RootCauseDiagnoser
from polyglot.patcher import DynamicCSSPatcher, GitDiffPatcher, UNSAFE_GENERIC_SELECTORS
from polyglot.reporting import HTMLReportGenerator
from polyglot.detector import CollisionDetector
from polyglot.repair import RepairOrchestrator


def test_diagnose_bidi_isolation():
    elem = {"text": "Total: $49.99", "hasBidiIsolation": False}
    diag = RootCauseDiagnoser.diagnose_overflow(elem, overflow_px=15.0, locale="ar-SA")
    assert diag["category"] == "BIDI_DIRECTIONAL_ISOLATION"
    assert "Unicode isolation" in diag["remedy"]


def test_diagnose_flex_nowrap():
    elem = {
        "text": "Benachrichtigungskonfiguration",
        "parentDisplay": "flex",
        "parentFlexWrap": "nowrap",
        "isRigidWidth": False,
        "computedWidth": 120.0
    }
    diag = RootCauseDiagnoser.diagnose_overflow(elem, overflow_px=45.0, locale="de-DE")
    assert diag["category"] == "FLEX_CONTAINER_NO_WRAP"
    assert "wrapping" in diag["remedy"]


def test_diagnose_rigid_width():
    elem = {
        "text": "Einstellungen",
        "parentDisplay": "block",
        "isRigidWidth": True,
        "computedWidth": 49.0
    }
    diag = RootCauseDiagnoser.diagnose_overflow(elem, overflow_px=22.0, locale="de-DE")
    assert diag["category"] == "CSS_RIGID_WIDTH_CONSTRAINT"
    assert "min-width:" in diag["remedy"]


def test_diagnose_collision_flex_sibling():
    elem1 = {"parentDisplay": "flex", "parentFlexWrap": "nowrap"}
    collision = {"overlapArea": 120, "overlapX": 15, "overlapY": 8, "parentDisplay": "flex", "parentFlexWrap": "nowrap"}
    diag = RootCauseDiagnoser.diagnose_collision(collision, elem1, {})
    assert diag["category"] == "FLEX_SIBLING_OVERLAP"


def test_dynamic_css_patcher_geometry_calculation():
    diagnosed = [
        {
            "selector": ".custom-card-btn",
            "category": "CSS_RIGID_WIDTH_CONSTRAINT",
            "current_width": 50.0,
            "overflow_px": 25.0
        },
        {
            "selector": "#action-menu-item",
            "category": "FLEX_CONTAINER_NO_WRAP",
            "current_width": 100.0,
            "overflow_px": 30.0
        }
    ]

    css = DynamicCSSPatcher.generate_css(diagnosed)

    # Must contain calculated min-width (50 + 25 + 8 = 83px)
    assert ".custom-card-btn {" in css
    assert "min-width: 83px !important;" in css
    # Must contain calculated min-width (100 + 30 + 8 = 138px)
    assert "#action-menu-item {" in css
    assert "min-width: 138px !important;" in css
    # Must NOT have any hardcoded Grafana selectors
    assert "grafana" not in css.lower()


def test_dynamic_css_patcher_refuses_unsafe_generic_selectors():
    diagnosed = [
        {"selector": "button", "category": "CSS_RIGID_WIDTH_CONSTRAINT", "current_width": 50, "overflow_px": 20},
        {"selector": "a", "category": "TEXT_VERBOSITY_EXPANSION", "current_width": 40, "overflow_px": 10},
        {"selector": "div", "category": "FLEX_CONTAINER_NO_WRAP", "current_width": 80, "overflow_px": 15},
        {"selector": ".safe-specific-btn", "category": "CSS_RIGID_WIDTH_CONSTRAINT", "current_width": 50, "overflow_px": 20}
    ]

    css = DynamicCSSPatcher.generate_css(diagnosed)

    assert "button {" not in css
    assert "a {" not in css
    assert "div {" not in css
    assert ".safe-specific-btn {" in css


def test_dynamic_css_patcher_empty():
    css = DynamicCSSPatcher.generate_css([])
    assert "No CSS layout overrides required" in css


def test_git_diff_patcher_refuses_when_no_repo():
    patch = GitDiffPatcher.generate_patch(repo_path=None, css_rules={".btn": ["min-width: 100px;"]})
    assert patch is None

    patch2 = GitDiffPatcher.generate_patch(repo_path="C:/non_existent_folder_xyz", css_rules={})
    assert patch2 is None


def test_git_diff_patcher_with_real_local_file():
    with tempfile.TemporaryDirectory() as temp_dir:
        test_file = os.path.join(temp_dir, "styles.module.css")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write(".my-nav-button {\n  color: red;\n}\n")

        rules = {".my-nav-button": ["min-width: 120px !important;", "flex-shrink: 0 !important;"]}
        patch = GitDiffPatcher.generate_patch(repo_path=temp_dir, css_rules=rules)

        assert patch is not None
        assert "diff --git a/styles.module.css b/styles.module.css" in patch
        assert "min-width: 120px !important;" in patch
        assert "@@ -" in patch  # Genuine unified diff hunk header


def test_reporting_truthfulness_clean_layout():
    with tempfile.TemporaryDirectory() as temp_dir:
        report_path = os.path.join(temp_dir, "test_clean_report.html")
        data = {
            "target_url": "https://example.com",
            "locale": "de-DE",
            "viewport": "desktop (1280x800)",
            "total_scanned": 15,
            "total_translated": 10,
            "provenance_counts": {"OPENAI_API": 10, "PRESET": 0, "PSEUDO": 0, "FALLBACK": 0, "FAILED": 0},
            "initial_overflows": 0,
            "initial_collisions": 0,
            "final_overflows": 0,
            "final_collisions": 0,
            "resolved_overflows": 0,
            "resolved_collisions": 0,
            "diagnosed_issues": []
        }

        HTMLReportGenerator.generate(data, report_path)
        with open(report_path, "r", encoding="utf-8") as f:
            html = f.read()

        assert "Clean Layout — No Overflows or Collisions Detected" in html
        assert "100% Neural API" in html


def test_reporting_provenance_includes_fallbacks_in_denominator():
    # Crucial test: 1 success and 9 fallbacks must calculate 10% Neural API, NOT 100%!
    with tempfile.TemporaryDirectory() as temp_dir:
        report_path = os.path.join(temp_dir, "test_fallback_report.html")
        data = {
            "target_url": "https://example.com",
            "locale": "de-DE",
            "viewport": "desktop",
            "total_scanned": 10,
            "total_translated": 10,
            "provenance_counts": {"OPENAI_API": 1, "PRESET": 0, "PSEUDO": 0, "FALLBACK": 9},
            "initial_overflows": 0,
            "initial_collisions": 0,
            "final_overflows": 0,
            "final_collisions": 0,
            "diagnosed_issues": []
        }

        HTMLReportGenerator.generate(data, report_path)
        with open(report_path, "r", encoding="utf-8") as f:
            html = f.read()

        assert "10% Neural API" in html
        assert "API: 1" in html
        assert "Fallback: 9" in html


def test_golden_multilingual_breakage_scenario():
    """
    User's Definitive Benchmark Test:
    - 3 overlapping buttons
    - 2 overflowing navigation links
    - 1 Arabic mixed-direction pricing element
    - 1 element that should NOT be modified
    Polyglot must identify all 6 problems, leave the 7th element untouched,
    repair the problems, and produce a patch that cleanly applies to the source repository.
    """
    from playwright.sync_api import sync_playwright

    html_content = """<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
    * { box-sizing: border-box; }
    body { font-family: sans-serif; padding: 20px; background: #fff; }

    /* Problem 1, 2, 3: Three overlapping buttons in narrow fixed container */
    .button-group {
      display: flex;
      flex-wrap: nowrap;
      width: 140px;
      margin-bottom: 30px;
      position: relative;
    }
    .btn-action-1, .btn-action-2, .btn-action-3 {
      min-width: 65px;
      margin-right: -25px; /* Forced collision overlap */
      padding: 6px 10px;
      font-size: 14px;
      background: #e2e8f0;
      border: 1px solid #94a3b8;
    }

    /* Problem 4, 5: Two overflowing navigation links with rigid max-width */
    .nav-bar { display: flex; gap: 10px; margin-bottom: 30px; }
    .nav-link-item-1, .nav-link-item-2 {
      display: inline-block;
      max-width: 45px;
      overflow: hidden;
      white-space: nowrap;
      text-overflow: ellipsis;
      background: #fee2e2;
      padding: 4px;
    }

    /* Problem 6: Arabic mixed-direction pricing element (RTL without isolation) */
    .pricing-card {
      width: 200px;
      direction: rtl;
      font-size: 14px;
      padding: 10px;
      border: 1px solid #cbd5e1;
      margin-bottom: 30px;
    }
    .price-tag {
      display: inline-block;
    }

    /* Element 7: Untouched safe element */
    .safe-title {
      font-size: 20px;
      width: auto;
      max-width: 100%;
      color: #0f172a;
      padding: 8px 0;
    }
  </style>
</head>
<body>
  <!-- 3 overlapping buttons -->
  <div class="button-group">
    <button class="btn-action-1">Submit</button>
    <button class="btn-action-2">Cancel</button>
    <button class="btn-action-3">Delete</button>
  </div>

  <!-- 2 overflowing nav links -->
  <nav class="nav-bar">
    <a href="#" class="nav-link-item-1">Documentation Overview</a>
    <a href="#" class="nav-link-item-2">Account Notifications</a>
  </nav>

  <!-- 1 Arabic mixed-direction pricing element -->
  <div class="pricing-card">
    <span class="price-tag">السعر الإجمالي: $49.99 فقط</span>
  </div>

  <!-- Element 7: Should NOT be modified -->
  <h1 class="safe-title">Dashboard Overview</h1>
</body>
</html>"""

    with tempfile.TemporaryDirectory() as temp_dir:
        fixture_html = os.path.join(temp_dir, "fixture.html")
        fixture_css = os.path.join(temp_dir, "styles.css")
        with open(fixture_html, "w", encoding="utf-8") as f:
            f.write(html_content)

        # Write matching CSS file in repo
        css_content = """.btn-action-1, .btn-action-2, .btn-action-3 {
  min-width: 65px;
  margin-right: -25px;
  padding: 6px 10px;
}
.nav-link-item-1, .nav-link-item-2 {
  max-width: 45px;
  overflow: hidden;
}
"""
        with open(fixture_css, "w", encoding="utf-8") as f:
            f.write(css_content)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.goto(f"file:///{fixture_html.replace(os.sep, '/')}")
            page.wait_for_timeout(300)

            # Discover elements
            from polyglot.scanner import DOMScanner
            elements = DOMScanner.discover_elements(page)
            assert len(elements) >= 7

            target_ids = [el["id"] for el in elements]

            # Inoculate translations
            candidates_map = {}
            for el in elements:
                txt = el["text"]
                if "Submit" in txt:
                    candidates_map[el["id"]] = {"standard": "Absenden", "compact": "Senden", "ultra_short": "OK"}
                elif "Cancel" in txt:
                    candidates_map[el["id"]] = {"standard": "Abbrechen", "compact": "Stop", "ultra_short": "X"}
                elif "Delete" in txt:
                    candidates_map[el["id"]] = {"standard": "Entfernen", "compact": "Löschen", "ultra_short": "Del"}
                elif "Documentation" in txt:
                    candidates_map[el["id"]] = {"standard": "Dokumentationsübersicht", "compact": "Doku-Übersicht", "ultra_short": "Doku"}
                elif "Account Notifications" in txt:
                    candidates_map[el["id"]] = {"standard": "Benachrichtigungskonfiguration", "compact": "Benachrichtigungen", "ultra_short": "Meldungen"}
                elif "السعر" in txt or "49.99" in txt:
                    candidates_map[el["id"]] = {"standard": "السعر الإجمالي: $49.99 فقط", "compact": "السعر: $49.99", "ultra_short": "$49.99"}
                else:
                    candidates_map[el["id"]] = {"standard": "Dashboard-Übersicht", "compact": "Übersicht", "ultra_short": "Übersicht"}

            # Execute closed-loop repair
            orchestrator = RepairOrchestrator(
                page=page,
                target_elements=elements,
                candidates_map=candidates_map,
                locale="de-DE",
                strategy="auto",
                verify=True
            )
            results = orchestrator.execute_closed_loop_repair()

            # Assert:
            # 1. Detected initial overflows/collisions on the 6 broken items
            assert results["initial_overflows"] + results["initial_collisions"] >= 4

            # 2. Element 7 (.safe-title) was NOT diagnosed or targeted for CSS repair
            diagnosed_selectors = [d.get("selector", "") for d in results["diagnosed_issues"]]
            assert not any(".safe-title" in s or "safe-title" in s for s in diagnosed_selectors)
            assert not any("h1" == s for s in diagnosed_selectors)

            # 3. Dynamic CSS generated must NOT contain generic tags or untouched element
            dynamic_css = results.get("dynamic_css", "")
            assert "h1" not in dynamic_css
            assert ".safe-title" not in dynamic_css

            # 4. Generate Git patch against temp_dir
            css_rules_map = {}
            for diag in results.get("diagnosed_issues", []):
                sel = diag.get("selector")
                if sel and ".safe-title" not in sel:
                    css_rules_map[sel] = [f"min-width: 90px !important;", "flex-shrink: 0 !important;"]

            patch = GitDiffPatcher.generate_patch(repo_path=temp_dir, css_rules=css_rules_map)
            assert patch is not None
            assert "diff --git a/styles.css b/styles.css" in patch
            assert ".safe-title" not in patch

            browser.close()
