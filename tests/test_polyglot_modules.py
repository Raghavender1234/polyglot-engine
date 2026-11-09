"""
Unit Tests for Polyglot Modular Architecture:
- RootCauseDiagnoser (computed layout constraint analysis & fresh styling)
- DynamicCSSPatcher (dynamic, non-hardcoded CSS rule generation & generic selector protection)
- GitDiffPatcher (honest source-aware patching with difflib unified diffs & strict git apply validation)
- HTMLReportGenerator (evidence-based truthful reporting with fallback in denominator & safe HTML escaping)
- Golden Multilingual Benchmark:
  * 3 overlapping buttons
  * 2 overflowing navigation links
  * 1 Arabic mixed-direction pricing element
  * 1 untouched element
"""

import os
import re
import difflib
import subprocess
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
            "total_evaluated": 10,
            "total_skipped": 5,
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
        assert "15 elements discovered | 10 tested | 5 skipped" in html


def test_reporting_provenance_includes_fallbacks_in_denominator():
    # Crucial test: 1 success and 9 fallbacks must calculate 10% Neural API, NOT 100%!
    with tempfile.TemporaryDirectory() as temp_dir:
        report_path = os.path.join(temp_dir, "test_fallback_report.html")
        data = {
            "target_url": "https://example.com",
            "locale": "de-DE",
            "viewport": "desktop",
            "total_scanned": 10,
            "total_evaluated": 10,
            "total_skipped": 0,
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


def test_reporting_html_escaping_security():
    # Verify that malicious website input strings are escaped to prevent XSS in generated audit reports
    with tempfile.TemporaryDirectory() as temp_dir:
        report_path = os.path.join(temp_dir, "test_xss_report.html")
        data = {
            "target_url": 'https://example.com/"><script>alert(1)</script>',
            "locale": "de-DE",
            "viewport": 'desktop"><b onmouseover=alert(1)>',
            "total_scanned": 1,
            "total_evaluated": 1,
            "total_skipped": 0,
            "provenance_counts": {"OPENAI_API": 1},
            "initial_overflows": 0,
            "initial_collisions": 0,
            "final_overflows": 0,
            "final_collisions": 0,
            "dynamic_css": 'body { content: "</script><script>alert(2)</script>"; }',
            "diagnosed_issues": []
        }

        HTMLReportGenerator.generate(data, report_path)
        with open(report_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        assert "<script>alert(1)</script>" not in html_content
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html_content


def test_reporting_explicit_unverified_status():
    with tempfile.TemporaryDirectory() as temp_dir:
        report_path = os.path.join(temp_dir, "test_unverified_report.html")
        data = {
            "target_url": "https://example.com",
            "locale": "de-DE",
            "viewport": "desktop",
            "verified": False,
            "total_scanned": 5,
            "total_evaluated": 5,
            "total_skipped": 0,
            "provenance_counts": {"OPENAI_API": 5},
            "initial_overflows": 2,
            "initial_collisions": 1,
            "final_overflows": None,
            "final_collisions": None,
            "diagnosed_issues": []
        }

        HTMLReportGenerator.generate(data, report_path)
        with open(report_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        assert "Unverified Repairs Applied" in html_content
        assert "2 → (Unverified)" in html_content
        assert "1 → (Unverified)" in html_content


def test_golden_multilingual_breakage_scenario():
    """
    User's Definitive Benchmark Test:
    - 3 overlapping buttons
    - 2 overflowing navigation links
    - 1 Arabic mixed-direction pricing element
    - 1 element that should NOT be modified
    Proves:
    1. Identification of all 6 problems (including BiDi classification for RTL pricing)
    2. Untouched element 7 remains completely unchanged in DOM, CSS and patch
    3. All 6 problems repaired in browser
    4. Generated Git patch applies cleanly to source repository with git apply --check and git apply.
    """
    from playwright.sync_api import sync_playwright

    html_content = """<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <link rel="stylesheet" href="styles.css">
  <style>
    * { box-sizing: border-box; }
    body { font-family: sans-serif; padding: 20px; background: #fff; }
  </style>
</head>
<body>
  <!-- 3 overlapping buttons in fixed width row -->
  <div class="button-group">
    <button class="btn-action-1">Submit</button>
    <button class="btn-action-2">Cancel</button>
    <button class="btn-action-3">Delete</button>
  </div>

  <!-- 2 overflowing nav links with rigid max-width -->
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

    css_content = """/* Component Styles */
.button-group {
  display: flex;
  flex-wrap: nowrap;
  width: 140px;
  margin-bottom: 30px;
}
.btn-action-1 {
  min-width: 65px;
  margin-right: -25px; /* Overlap collision */
  padding: 6px 10px;
}
.btn-action-2 {
  min-width: 65px;
  margin-right: -25px; /* Overlap collision */
  padding: 6px 10px;
}
.btn-action-3 {
  min-width: 65px;
  padding: 6px 10px;
}
.nav-bar {
  display: flex;
  gap: 10px;
  margin-bottom: 30px;
}
.nav-link-item-1 {
  display: inline-block;
  max-width: 45px;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}
.nav-link-item-2 {
  display: inline-block;
  max-width: 45px;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}
.pricing-card {
  width: 200px;
  margin-bottom: 30px;
}
.price-tag {
  display: inline-block;
}
.safe-title {
  font-size: 20px;
  width: auto;
  max-width: 100%;
}
"""

    with tempfile.TemporaryDirectory() as temp_dir:
        fixture_html = os.path.join(temp_dir, "fixture.html")
        fixture_css = os.path.join(temp_dir, "styles.css")
        with open(fixture_html, "w", encoding="utf-8") as f:
            f.write(html_content)
        with open(fixture_css, "w", encoding="utf-8") as f:
            f.write(css_content)

        # Initialize clean Git repository in temp_dir to test genuine patch application
        subprocess.run(["git", "init"], cwd=temp_dir, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test Runner"], cwd=temp_dir, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@polyglot.ai"], cwd=temp_dir, check=True, capture_output=True)
        subprocess.run(["git", "add", "."], cwd=temp_dir, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial baseline styles"], cwd=temp_dir, check=True, capture_output=True)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.goto(f"file:///{fixture_html.replace(os.sep, '/')}")
            page.wait_for_timeout(300)

            # Discover elements
            from polyglot.scanner import DOMScanner
            elements = DOMScanner.discover_elements(page)
            assert len(elements) >= 7

            # Capture initial untouched text of Element 7
            untouched_initial_text = page.evaluate("() => document.querySelector('.safe-title').textContent.trim()")
            assert untouched_initial_text == "Dashboard Overview"

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
                    candidates_map[el["id"]] = {"standard": "Dashboard Overview", "compact": "Dashboard", "ultra_short": "Dash"}

            # Execute closed-loop repair with repo_path for source patch and reload verification
            orchestrator = RepairOrchestrator(
                page=page,
                target_elements=elements,
                candidates_map=candidates_map,
                locale="de-DE",
                strategy="auto",
                verify=True,
                repo_path=temp_dir
            )
            results = orchestrator.execute_closed_loop_repair()

            # -------------------------------------------------------------
            # PROOF 1: Accurate Problem Identification of all 6 problems
            # -------------------------------------------------------------
            initial_diagnosed = results.get("initial_diagnosed_issues", results["diagnosed_issues"])
            initial_diag_selectors = [d.get("selector", "") for d in initial_diagnosed]

            # 2 nav links identified with overflows:
            assert any("nav-link-item-1" in s for s in initial_diag_selectors), f"nav-link-item-1 missing: {initial_diag_selectors}"
            assert any("nav-link-item-2" in s for s in initial_diag_selectors), f"nav-link-item-2 missing: {initial_diag_selectors}"

            # All 3 individual buttons identified in collisions:
            assert any("btn-action-1" in s for s in initial_diag_selectors), f"btn-action-1 missing: {initial_diag_selectors}"
            assert any("btn-action-2" in s for s in initial_diag_selectors), f"btn-action-2 missing: {initial_diag_selectors}"
            assert any("btn-action-3" in s for s in initial_diag_selectors), f"btn-action-3 missing: {initial_diag_selectors}"

            # Arabic pricing element identified as In-Browser BiDi Defect directly by detector:
            bidi_issues = [d for d in initial_diagnosed if d.get("category") == "BIDI_DIRECTIONAL_ISOLATION"]
            assert len(bidi_issues) >= 1, f"Expected BiDi issues in browser detection: {initial_diagnosed}"
            assert any("price-tag" in d.get("selector", "") for d in bidi_issues), f"price-tag missing in BiDi issues: {bidi_issues}"
            assert results["initial_bidi_defects"] >= 1

            # -------------------------------------------------------------
            # PROOF 2: All 6 Defects Repaired & Verified in Browser
            # -------------------------------------------------------------
            assert results["verified"] is True
            assert results["final_overflows"] == 0
            assert results["final_collisions"] == 0
            assert results["final_bidi_defects"] == 0
            assert results["all_cleared"] is True

            # -------------------------------------------------------------
            # PROOF 3: Element 7 (.safe-title) Left Completely Untouched
            # -------------------------------------------------------------
            untouched_final_text = page.evaluate("() => document.querySelector('.safe-title').textContent.trim()")
            assert untouched_final_text == "Dashboard Overview"
            assert not any(".safe-title" in s or "safe-title" in s for s in initial_diag_selectors)
            assert not any("h1" == s for s in initial_diag_selectors)

            dynamic_css = results.get("dynamic_css", "")
            assert ".safe-title" not in dynamic_css
            assert "h1" not in dynamic_css

            # -------------------------------------------------------------
            # PROOF 4: Genuine Closed-Loop Source Patch & Reload Verification
            # -------------------------------------------------------------
            assert results["source_patch_verified"] is True
            patch = results["git_patch"]
            assert patch is not None
            assert "diff --git a/styles.css b/styles.css" in patch
            assert "@@ -" in patch  # Valid unified diff header with real line offsets

            # Ensure .safe-title is NEVER modified by the patch (no additions or deletions for safe-title)
            patch_additions = [line for line in patch.splitlines() if line.startswith("+") and not line.startswith("+++")]
            patch_deletions = [line for line in patch.splitlines() if line.startswith("-") and not line.startswith("---")]
            assert not any("safe-title" in line for line in patch_additions)
            assert not any("safe-title" in line for line in patch_deletions)

            # Verify that styles.css on disk was actually updated with the expected declarations:
            with open(fixture_css, "r", encoding="utf-8") as f:
                updated_css = f.read()

            # Verify BiDi declarations in .price-tag
            assert "unicode-bidi: isolate !important;" in updated_css

            # Verify layout declarations in buttons and nav
            assert "min-width:" in updated_css
            assert "margin-right: 8px !important;" in updated_css

            # Verify that .safe-title rule in styles.css was left completely untouched:
            assert ".safe-title {\n  font-size: 20px;\n  width: auto;\n  max-width: 100%;\n}" in updated_css
            safe_block = updated_css[updated_css.index(".safe-title"):]
            assert "min-width" not in safe_block
            assert "margin" not in safe_block

            browser.close()


def test_bidi_visual_detection_false_positive_immunity():
    """
    Proves that correctly rendered BiDi content (e.g. using <bdi> or dir="auto")
    is NOT falsely flagged as a defect by CollisionDetector.
    """
    from playwright.sync_api import sync_playwright

    html = """<!DOCTYPE html>
    <html>
    <body>
      <!-- Correct Case 1: isolated price using <bdi> in Arabic context -->
      <div data-polyglot-id="safe-price-1" dir="auto" class="price-box">
        السعر: <bdi>$49.99</bdi>
      </div>

      <!-- Correct Case 2: isolated brand name in RTL context -->
      <div data-polyglot-id="safe-price-2" dir="rtl" class="brand-box">
        <bdi>Polyglot</bdi> في الواجهة
      </div>

      <!-- Correct Case 3: CSS isolate on mixed text with numbers -->
      <div data-polyglot-id="safe-price-3" style="unicode-bidi: isolate; direction: ltr;" class="isolated-box">
        Arabic: <bdi>مرحبا 2026</bdi>
      </div>
    </body>
    </html>"""

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content(html)

        detection = CollisionDetector.detect(page, ["safe-price-1", "safe-price-2", "safe-price-3"])
        assert detection["bidiCount"] == 0, f"Expected 0 BiDi defects for correctly isolated content, got: {detection['bidiIssues']}"
        assert len(detection["bidiIssues"]) == 0
        browser.close()


def test_bidi_visual_detection_catches_unisolated_inversion():
    """
    Proves that genuinely broken BiDi rendering (unisolated $ flipped across 49.99 in LTR container)
    is accurately detected as CURRENCY_SYMBOL_INVERSION.
    """
    from playwright.sync_api import sync_playwright

    html = """<!DOCTYPE html>
    <html>
    <body>
      <!-- Genuinely broken: LTR context without isolation causes $ to jump to right of 49.99 -->
      <div data-polyglot-id="broken-price" style="direction: ltr; font-size: 20px; width: 300px;">
        السعر: $49.99
      </div>
    </body>
    </html>"""

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content(html)

        detection = CollisionDetector.detect(page, ["broken-price"])
        assert detection["bidiCount"] == 1, f"Expected 1 BiDi defect for broken currency, got: {detection}"
        issue = detection["bidiIssues"][0]
        assert issue["category"] == "BIDI_DIRECTIONAL_ISOLATION"
        assert issue["type"] == "CURRENCY_SYMBOL_INVERSION"
        assert "flipped to the wrong side" in issue["explanation"]
        browser.close()


def test_detector_whole_dom_custom_elements_collision():
    """
    Proves that collision detection is NOT limited to a predefined tag list.
    Detects collisions between a translated button and a custom Web Component element.
    """
    from playwright.sync_api import sync_playwright

    html = """<!DOCTYPE html>
    <html>
    <head>
      <style>
        .container { position: relative; width: 400px; height: 100px; }
        .action-btn { position: absolute; left: 10px; top: 10px; width: 120px; height: 40px; }
        custom-dashboard-widget { display: block; position: absolute; left: 30px; top: 10px; width: 150px; height: 40px; background: blue; }
      </style>
    </head>
    <body>
      <div class="container">
        <button data-polyglot-id="btn-overlap" class="action-btn">Action Button</button>
        <custom-dashboard-widget class="dashboard-panel">Dashboard Widget</custom-dashboard-widget>
      </div>
    </body>
    </html>"""

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content(html)

        detection = CollisionDetector.detect(page, ["btn-overlap"])
        assert detection["collisionCount"] >= 1, "Expected collision with custom element"
        col = detection["collisions"][0]
        assert "custom-dashboard-widget" in col["elem2"] or "dashboard-panel" in col["selector2"]
        browser.close()


def test_patcher_targets_responsible_stylesheet_only():
    """
    Proves that GitDiffPatcher targets ONLY the responsible stylesheet identified by the browser,
    leaving other stylesheets with identical selectors untouched.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        btn_css_path = os.path.join(temp_dir, "button.css")
        nav_css_path = os.path.join(temp_dir, "nav.css")

        with open(btn_css_path, "w", encoding="utf-8") as f:
            f.write(".action-item {\n  width: 50px;\n}\n")

        with open(nav_css_path, "w", encoding="utf-8") as f:
            f.write(".action-item {\n  color: blue;\n}\n")

        issues = [
            {
                "selector": ".action-item",
                "category": "CSS_RIGID_WIDTH_CONSTRAINT",
                "current_width": 50.0,
                "overflow_px": 20.0,
                "target_stylesheet": "button.css"  # Browser identified button.css as the source!
            }
        ]

        patch = GitDiffPatcher.generate_patch(repo_path=temp_dir, css_rules_or_issues=issues)
        assert patch is not None
        assert "button.css" in patch
        assert "nav.css" not in patch  # Never modifies the irrelevant stylesheet!

