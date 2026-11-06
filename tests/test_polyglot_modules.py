"""
Unit Tests for Polyglot Modular Architecture:
- RootCauseDiagnoser (computed layout constraint analysis)
- DynamicCSSPatcher (dynamic, non-hardcoded CSS rule generation)
- GitDiffPatcher (honest source-aware patching)
- HTMLReportGenerator (evidence-based truthful reporting)
"""

import os
import tempfile
import pytest

from polyglot.diagnosis import RootCauseDiagnoser
from polyglot.patcher import DynamicCSSPatcher, GitDiffPatcher
from polyglot.reporting import HTMLReportGenerator


def test_diagnose_bidi_isolation():
    elem = {"text": "Total: $49.99"}
    diag = RootCauseDiagnoser.diagnose_overflow(elem, overflow_px=15.0, locale="ar-SA")
    assert diag["category"] == "BIDI_DIRECTIONAL_ISOLATION"
    assert "Unicode isolation" in diag["remedy"]


def test_diagnose_flex_nowrap():
    elem = {
        "text": "Benachrichtigungskonfiguration",
        "parentDisplay": "flex",
        "parentFlexWrap": "nowrap",
        "isRigidWidth": False,
        "contentWidth": 120.0
    }
    diag = RootCauseDiagnoser.diagnose_overflow(elem, overflow_px=45.0, locale="de-DE")
    assert diag["category"] == "FLEX_CONTAINER_NO_WRAP"
    assert "wrapping" in diag["remedy"]


def test_diagnose_rigid_width():
    elem = {
        "text": "Einstellungen",
        "parentDisplay": "block",
        "isRigidWidth": True,
        "contentWidth": 49.0
    }
    diag = RootCauseDiagnoser.diagnose_overflow(elem, overflow_px=22.0, locale="de-DE")
    assert diag["category"] == "CSS_RIGID_WIDTH_CONSTRAINT"
    assert "min-width:" in diag["remedy"]


def test_diagnose_collision_flex_sibling():
    elem1 = {"parentDisplay": "flex", "parentFlexWrap": "nowrap"}
    collision = {"overlapArea": 120, "overlapX": 15, "overlapY": 8}
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


def test_dynamic_css_patcher_empty():
    css = DynamicCSSPatcher.generate_css([])
    assert "No CSS layout overrides required" in css


def test_git_diff_patcher_refuses_when_no_repo():
    # Honesty constraint: never fabricate diffs when repo is absent
    patch = GitDiffPatcher.generate_patch(repo_path=None, css_rules={".btn": ["min-width: 100px;"]})
    assert patch is None

    patch2 = GitDiffPatcher.generate_patch(repo_path="C:/non_existent_folder_xyz", css_rules={})
    assert patch2 is None


def test_git_diff_patcher_with_real_local_file():
    with tempfile.TemporaryDirectory() as temp_dir:
        test_file = os.path.join(temp_dir, "styles.module.css")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write(".my-nav-button {\n  color: red;\n}\n")

        rules = {".my-nav-button": ["min-width: 120px;", "flex-shrink: 0;"]}
        patch = GitDiffPatcher.generate_patch(repo_path=temp_dir, css_rules=rules)

        assert patch is not None
        assert "diff --git a/styles.module.css b/styles.module.css" in patch
        assert "+.my-nav-button {" in patch
        assert "+  min-width: 120px;" in patch


def test_reporting_truthfulness_clean_layout():
    with tempfile.TemporaryDirectory() as temp_dir:
        report_path = os.path.join(temp_dir, "test_clean_report.html")
        data = {
            "target_url": "https://example.com",
            "locale": "de-DE",
            "viewport": "desktop (1280x800)",
            "total_scanned": 15,
            "total_translated": 10,
            "provenance_counts": {"OPENAI_API": 10, "PRESET": 0, "PSEUDO": 0, "FAILED": 0},
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

        # Must report clean layout, NOT "Repairs successfully applied"
        assert "Clean Layout — No Overflows or Collisions Detected" in html
        assert "100% OpenAI API" in html
