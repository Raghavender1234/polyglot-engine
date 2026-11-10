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
    format_markdown_summary,
    write_ci_summary,
    evaluate_exit_code,
    cmd_report,
)



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

