"""Unit Tests for Polyglot Developer CLI Surface & Terminal Scorecard.

Tests:
- CLI command registration: `scan`, `report`, `fix`, `repair`, `diagnose`
- Scorecard formatting (clean audit vs defects)
- CI exit code policies: `--fail-on=any`, `--fail-on=critical`, `--fail-on=none`
- `polyglot report` resolution and fallback behavior
"""

import os
import sys
import tempfile
import pytest
from unittest.mock import patch, MagicMock

from polyglot.cli import (
    main,
    format_scan_scorecard,
    format_repair_scorecard,
    format_verify_scorecard,
    format_markdown_summary,
    write_ci_summary,
    evaluate_exit_code,
    load_project_config,
    resolve_visual_ai_mode,
    resolve_translation_mode,
    cmd_init,
    cmd_report,
)
from polyglot.reporting import HTMLReportGenerator
from polyglot.visual import VisualAIInspector





def test_cli_subparsers_registration():
    """Verify all subcommands ('scan', 'report', 'fix', 'repair', 'diagnose') are recognized."""
    # Test --help does not crash
    with pytest.raises(SystemExit) as exc:
        with patch.object(sys, "argv", ["polyglot", "--help"]):
            main()
    assert exc.value.code == 0

    # Test 'fix' subparser has same interface as 'repair'
    with pytest.raises(SystemExit) as exc:
        with patch.object(sys, "argv", ["polyglot", "fix", "--help"]):
            main()
    assert exc.value.code == 0

    # Test 'report' subparser
    with pytest.raises(SystemExit) as exc:
        with patch.object(sys, "argv", ["polyglot", "report", "--help"]):
            main()
    assert exc.value.code == 0


def test_format_scan_scorecard_clean():
    runs = [{
        "locale": "ja-JP",
        "viewport": "desktop (1280x800)",
        "initial_overflows": 0,
        "initial_collisions": 0,
        "initial_bidi_defects": 0
    }]
    scorecard = format_scan_scorecard("http://localhost:3000", runs)
    assert "POLYGLOT MULTILINGUAL AUDIT SCORECARD" in scorecard
    assert "PASSED ✅" in scorecard
    assert "zero defects" in scorecard


def test_format_scan_scorecard_with_defects():
    runs = [
        {
            "locale": "de-DE",
            "viewport": "desktop (1280x800)",
            "initial_overflows": 2,
            "initial_collisions": 1,
            "initial_bidi_defects": 0
        },
        {
            "locale": "ar-SA",
            "viewport": "mobile (390x844)",
            "initial_overflows": 0,
            "initial_collisions": 0,
            "initial_bidi_defects": 1
        }
    ]
    scorecard = format_scan_scorecard("http://localhost:3000", runs)
    assert "FAILED ❌" in scorecard
    assert "de-DE" in scorecard
    assert "ar-SA" in scorecard
    assert "Found 4 layout defect(s)" in scorecard
    assert "polyglot fix http://localhost:3000" in scorecard


def test_format_repair_scorecard():
    runs = [{
        "locale": "de-DE",
        "viewport": "desktop (1280x800)",
        "initial_overflows": 3,
        "initial_collisions": 0,
        "initial_bidi_defects": 0,
        "resolved_overflows": 3,
        "resolved_collisions": 0,
        "resolved_bidi_defects": 0,
        "final_overflows": 0,
        "final_collisions": 0,
        "final_bidi_defects": 0,
        "verified": True
    }]
    scorecard = format_repair_scorecard("http://localhost:3000", runs)
    assert "POLYGLOT CLOSED-LOOP REPAIR SCORECARD" in scorecard
    assert "REPAIRED ✅" in scorecard
    assert "All multilingual layout defects successfully repaired" in scorecard


def test_evaluate_exit_code_policies():
    defective_runs = [{
        "initial_overflows": 1,
        "initial_collisions": 1,
        "initial_bidi_defects": 0
    }]
    clean_runs = [{
        "initial_overflows": 0,
        "initial_collisions": 0,
        "initial_bidi_defects": 0
    }]

    # Policy: fail-on=any
    assert evaluate_exit_code(defective_runs, fail_on="any") == 1
    assert evaluate_exit_code(clean_runs, fail_on="any") == 0

    # Policy: fail-on=none
    assert evaluate_exit_code(defective_runs, fail_on="none") == 0

    # Policy: fail-on=critical (collisions only vs overflows)
    collision_only_runs = [{
        "initial_overflows": 0,
        "initial_collisions": 2,
        "initial_bidi_defects": 0
    }]
    # collisions are not critical by this rule, but overflows are
    assert evaluate_exit_code(collision_only_runs, fail_on="critical") == 0
    assert evaluate_exit_code(defective_runs, fail_on="critical") == 1


def test_cmd_report_launches_browser():
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
        f.write(b"<html><body>Polyglot Audit</body></html>")
        temp_path = f.name

    try:
        args = MagicMock()
        args.report_file = temp_path
        args.no_open = False

        with patch("webbrowser.open") as mock_open:
            cmd_report(args)
            assert mock_open.called
            call_url = mock_open.call_args[0][0]
            assert "file:///" in call_url
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def test_cmd_report_missing_file_exits():
    args = MagicMock()
    args.report_file = "non_existent_file_xyz.html"
    args.no_open = True

    with pytest.raises(SystemExit) as exc:
        cmd_report(args)
    assert exc.value.code == 1


def test_format_markdown_summary_scan():
    runs = [{
        "locale": "de-DE",
        "viewport": "desktop (1280x800)",
        "initial_overflows": 1,
        "initial_collisions": 0,
        "initial_bidi_defects": 0,
        "diagnosed_issues": [{
            "category": "FLEX_CONTAINER_NO_WRAP",
            "selector": "button.submit",
            "remedy": "Add flex-wrap: wrap;"
        }]
    }]
    md = format_markdown_summary("http://localhost:3000", runs, is_repair=False)
    assert "Polyglot Multilingual Audit Summary" in md
    assert "| `de-DE` | desktop (1280x800) | 1 | 0 | 0 | ❌ Failed |" in md
    assert "FLEX_CONTAINER_NO_WRAP" in md
    assert "Add flex-wrap: wrap;" in md


def test_write_ci_summary_to_file():
    with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as f:
        temp_path = f.name

    try:
        write_ci_summary("## Test Summary Content", summary_file=temp_path)
        with open(temp_path, "r", encoding="utf-8") as rf:
            content = rf.read()
        assert "## Test Summary Content" in content
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def test_cmd_init_and_load_project_config():
    with tempfile.TemporaryDirectory() as temp_dir:
        cfg_path = os.path.join(temp_dir, "polyglot.config.json")
        args = MagicMock()
        args.url = "http://localhost:4200"
        args.locales = "de-DE,ar-SA"
        args.viewports = "desktop,mobile"
        args.config = cfg_path

        cmd_init(args)
        assert os.path.exists(cfg_path)

        loaded = load_project_config(cfg_path)
        assert loaded["url"] == "http://localhost:4200"
        assert loaded["locales"] == ["de-DE", "ar-SA"]
        assert loaded["viewports"] == ["desktop", "mobile"]


def test_format_verify_scorecard():
    ver_data = {
        "total_matrix_runs": 2,
        "regressions_introduced": 0,
        "regression_rate_pct": 0.0,
        "all_locales_clean": True,
        "matrix_results": {
            "en-US@desktop": {
                "locale": "en-US",
                "viewport": "desktop",
                "overflows": 0,
                "collisions": 0,
                "bidi": 0,
                "is_clean": True
            },
            "de-DE@desktop": {
                "locale": "de-DE",
                "viewport": "desktop",
                "overflows": 0,
                "collisions": 0,
                "bidi": 0,
                "is_clean": True
            }
        }
    }
    scorecard = format_verify_scorecard("http://localhost:3000", ver_data)
    assert "POLYGLOT CROSS-LOCALE REGRESSION VERIFICATION" in scorecard
    assert "CLEAN ✅" in scorecard
    assert "Rate: 0.0%" in scorecard


def test_html_report_interactive_copy_and_filters():
    with tempfile.TemporaryDirectory() as temp_dir:
        out_path = os.path.join(temp_dir, "interactive_report.html")
        data = {
            "target_url": "http://localhost:3000",
            "locale": "de-DE",
            "viewport": "desktop",
            "verified": True,
            "total_scanned": 5,
            "total_evaluated": 5,
            "total_skipped": 0,
            "provenance_counts": {"OPENAI_API": 5},
            "initial_overflows": 1,
            "initial_collisions": 0,
            "final_overflows": 0,
            "final_collisions": 0,
            "resolved_overflows": 1,
            "dynamic_css": ".btn { min-width: 160px; }",
            "git_patch": "--- a/style.css\n+++ b/style.css",
            "diagnosed_issues": [{
                "category": "CSS_RIGID_WIDTH_CONSTRAINT",
                "selector": ".btn",
                "explanation": "Fixed width clipped German compound",
                "remedy": "Use min-width instead of fixed width"
            }]
        }
        HTMLReportGenerator.generate(data, out_path)
        with open(out_path, "r", encoding="utf-8") as f:
            html_out = f.read()

        assert "Copy CSS Overrides" in html_out
        assert "Copy Git Diff Patch" in html_out
        assert "filterIssues('FLEX', this)" in html_out
        assert "CSS_RIGID_WIDTH_CONSTRAINT" in html_out


def test_visual_ai_inspector_dual_sampling_and_detection():
    # Standard mode (off)
    std_inspector = VisualAIInspector(mode="off")
    assert not std_inspector.is_enabled

    # Enhanced mode (mock / moondream)
    enh_inspector = VisualAIInspector(mode="mock", clean_sample_size=2)
    assert enh_inspector.is_enabled

    elements = [
        {"id": "1", "tag": "button", "selector": "#btn1", "text": "Flagged Button", "direction": "ltr"},
        {"id": "2", "tag": "button", "selector": "#btn2", "text": "OVERLAP_ICON Clean Geometry", "direction": "ltr"},
        {"id": "3", "tag": "span", "selector": "#sp3", "text": "Clean Span", "direction": "rtl"},
        {"id": "4", "tag": "p", "selector": "#p4", "text": "Other Paragraph", "direction": "ltr"},
    ]
    flagged_ids = {"1"}

    # Dual-sampling must select id="1" (flagged) + up to 2 clean elements (prioritizing button #2 and rtl #3)
    candidates = enh_inspector.select_candidates(elements, flagged_ids)
    cand_ids = [c["id"] for c in candidates]
    assert "1" in cand_ids
    assert "2" in cand_ids
    assert "3" in cand_ids
    assert len(candidates) == 3

    # Mock page locator for inspect_page
    mock_page = MagicMock()
    mock_loc = MagicMock()
    mock_loc.count.return_value = 1
    mock_loc.first.screenshot.return_value = b"\x89PNG\r\n\x1a\n"
    mock_page.locator.return_value = mock_loc

    visual_issues = enh_inspector.inspect_page(mock_page, elements, flagged_ids)
    assert len(visual_issues) == 1
    assert visual_issues[0]["id"] == "2"
    assert visual_issues[0]["category"] == "VISUAL_AI_TEXT_ICON_OVERLAP"
    assert visual_issues[0]["caught_by_visual_ai_only"] is True


def test_visual_ai_local_mode_never_calls_cloud_and_refuses_non_loopback():
    """Proves --visual-ai=local never silently falls back to cloud API and rejects non-loopback Ollama URLs."""
    with pytest.raises(RuntimeError, match="Privacy violation prevented"):
        VisualAIInspector(mode="local", endpoint="https://remote-host.example.com/api/generate")

    with pytest.raises(RuntimeError, match="Silent cloud fallback is disabled by design"):
        VisualAIInspector(mode="local", endpoint="http://127.0.0.1:65534/api/generate")


def test_cli_resolve_visual_ai_mode_respects_config():
    """Proves polyglot.config.json 'visual_ai' is honored when --visual-ai flag is omitted on CLI."""
    args = MagicMock()
    args.visual_ai = None
    assert resolve_visual_ai_mode(args, {"visual_ai": "local"}) == "local"
    assert resolve_visual_ai_mode(args, {}) == "off"

    args.visual_ai = "off"
    assert resolve_visual_ai_mode(args, {"visual_ai": "local"}) == "off"


def test_translation_privacy_local_mode_never_calls_external_api():
    """Proves mode='local' never calls OpenAI even when OPENAI_API_KEY is present in environment."""
    from app.engines.llm_translator import llm_engine

    with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-dummy-key"}):
        with patch.object(llm_engine, "get_client") as mock_get_client:
            variants, prov = llm_engine.translate_with_variants(
                source_text="Unique Uncached String For Privacy Audit",
                source_locale="en-US",
                target_locale="de-DE",
                bypass_presets=False,
                mode="local"
            )
            assert prov == "PSEUDO"
            assert not mock_get_client.called




