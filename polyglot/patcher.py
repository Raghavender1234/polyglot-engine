"""
Polyglot Patcher — Dynamic CSS Generation & Source Repository Patching
Generates targeted, calculated CSS rules based on diagnosed element geometry and failure categories.
Enforces safety rules to prevent modifying broad generic HTML selectors.
When a local repository path is provided, locates the actual source stylesheet (never HTML),
modifies the stylesheet rule in memory using diagnosis-aware declarations, produces a genuine unified Git diff,
and STRICTLY validates it via `git apply --check`. If validation fails, the patch is rejected.
"""

import os
import re
import difflib
import subprocess
from typing import Dict, Any, List, Optional, Tuple, Union

UNSAFE_GENERIC_SELECTORS = {
    "button", "a", "div", "span", "p", "h1", "h2", "h3", "h4", "h5", "h6",
    "label", "input", "body", "html", "header", "nav", "aside", "table", "tr", "td", "th"
}

STYLESHEET_EXTENSIONS = (".css", ".scss", ".sass", ".less", ".module.css")

class DynamicCSSPatcher:
    @classmethod
    def generate_rules_map(cls, diagnosed_issues: List[Dict[str, Any]]) -> Dict[str, List[str]]:
        """
        Builds a diagnosis-aware CSS rule map.
        Each issue category receives its appropriate CSS declarations (e.g. BiDi receives isolation, not width).
        """
        rules = {}
        for issue in diagnosed_issues:
            sel = issue.get("selector", "").strip()
            if not sel or sel.lower() in UNSAFE_GENERIC_SELECTORS:
                # Refuse unsafe bare tags
                continue

            cat = issue.get("category", "")
            overflow_px = issue.get("overflow_px", 16.0)
            orig_w = issue.get("current_width", 60.0)
            needed_w = max(68.0, round(orig_w + overflow_px + 8.0))

            if cat == "CSS_RIGID_WIDTH_CONSTRAINT":
                rules[sel] = [
                    f"min-width: {needed_w:.0f}px !important;",
                    "max-width: none !important;",
                    "width: auto !important;",
                    "white-space: nowrap !important;"
                ]
            elif cat in ("FLEX_CONTAINER_NO_WRAP", "FLEX_SIBLING_OVERLAP", "ABSOLUTE_OR_FIXED_OVERLAP"):
                rules[sel] = [
                    f"min-width: {needed_w:.0f}px !important;",
                    "flex-shrink: 0 !important;",
                    "margin-right: 8px !important;"
                ]
            elif cat == "TEXT_VERBOSITY_EXPANSION":
                rules[sel] = [
                    "white-space: normal !important;",
                    "word-break: break-word !important;"
                ]
            elif cat == "BIDI_DIRECTIONAL_ISOLATION":
                rules[sel] = [
                    "unicode-bidi: isolate !important;",
                    "direction: rtl !important;",
                    "text-align: start !important;"
                ]
            else:
                rules[sel] = [
                    f"min-width: {needed_w:.0f}px !important;",
                    "flex-shrink: 0 !important;"
                ]

        return rules

    @classmethod
    def generate_css(cls, diagnosed_issues: List[Dict[str, Any]]) -> str:
        """
        Dynamically calculates targeted CSS rules derived directly from failing element geometry.
        Strictly rejects generic HTML tags to prevent cross-component layout damage.
        """
        rules = cls.generate_rules_map(diagnosed_issues)
        if not rules:
            return "/* Polyglot: No CSS layout overrides required. Layout verified cleanly. */\n"

        css_lines = ["/* Polyglot Engine Dynamically Calculated Layout Patch */"]
        css_lines.append("/* Rules generated from actual in-browser reflow geometry */\n")

        for sel, decls in rules.items():
            css_lines.append(f"{sel} {{")
            for d in decls:
                css_lines.append(f"  {d}")
            css_lines.append("}\n")

        return "\n".join(css_lines)


class GitDiffPatcher:
    @staticmethod
    def apply_modifications_to_css(content: str, selector: str, declarations: List[str]) -> Tuple[str, bool]:
        """
        Locates an existing CSS rule block for selector with exact word boundary.
        Performs property-aware replacement of conflicting declarations (e.g. overrides negative margin-right)
        or injects missing declarations before the closing brace.
        Returns (modified_content, modified_bool).
        """
        clean_sel = selector.strip()
        esc_sel = re.escape(clean_sel)
        pattern = re.compile(
            r"(^|\n)([ \t]*[^{]*?(?:(?<![\w-])" + esc_sel + r"(?![\w-]))[^{]*\{)([^}]*)(\})",
            re.MULTILINE
        )

        match = pattern.search(content)
        if not match:
            return content, False

        prefix = match.group(1)
        header = match.group(2)
        body = match.group(3)
        closing = match.group(4)

        indent = "  "
        updated_body = body
        modified = False

        for decl in declarations:
            decl_clean = decl.strip().rstrip(";")
            if ":" not in decl_clean:
                continue
            prop, val = [p.strip() for p in decl_clean.split(":", 1)]

            # Check if property already exists in rule body
            prop_regex = re.compile(r"(^[ \t]*" + re.escape(prop) + r"\s*:[^;]+;[^\n]*)", re.MULTILINE)
            if prop_regex.search(updated_body):
                # Replace existing property line with new declaration
                updated_body = prop_regex.sub(f"{indent}{decl}", updated_body)
                modified = True
            else:
                # Append before closing
                trimmed = updated_body.rstrip()
                updated_body = f"{trimmed}\n{indent}{decl}\n"
                modified = True

        if not modified or updated_body == body:
            return content, False

        new_content = content[:match.start()] + prefix + header + updated_body + closing + content[match.end():]
        return new_content, True

    @classmethod
    def generate_patch(
        cls,
        repo_path: Optional[str],
        css_rules_or_issues: Union[Dict[str, List[str]], List[Dict[str, Any]], None] = None,
        css_rules: Optional[Dict[str, List[str]]] = None
    ) -> Optional[str]:
        """
        Searches local source stylesheet files for the matching selector, modifies in memory,
        and produces a genuine unified Git diff patch with exact line numbers.
        If a list of diagnosed issues is provided, rules are generated in a diagnosis-aware manner,
        and modifications target the responsible stylesheet identified by the browser.
        Strictly validates the patch using git apply --check when in a git repo.
        If validation fails, strictly rejects and returns None.
        """
        target_input = css_rules_or_issues if css_rules_or_issues is not None else css_rules
        if not repo_path or not os.path.exists(repo_path) or not target_input:
            return None

        selector_to_sheet = {}
        if isinstance(target_input, list):
            resolved_rules = DynamicCSSPatcher.generate_rules_map(target_input)
            for issue in target_input:
                sel = issue.get("selector")
                sheet = issue.get("target_stylesheet")
                if sel and sheet:
                    selector_to_sheet[sel.strip()] = sheet.strip()
        else:
            resolved_rules = target_input

        if not resolved_rules:
            return None

        # Filter unsafe generic selectors
        safe_rules = {s: d for s, d in resolved_rules.items() if s.strip().lower() not in UNSAFE_GENERIC_SELECTORS}
        if not safe_rules:
            return None

        all_diffs = []

        # Find matching stylesheet files ONLY (never touch HTML or non-stylesheets)
        for root, _, files in os.walk(repo_path):
            if any(part in root for part in [".git", "node_modules", ".venv", "__pycache__"]):
                continue

            for file in files:
                if file.endswith(STYLESHEET_EXTENSIONS):
                    fpath = os.path.join(root, file)
                    rel_path = os.path.relpath(fpath, repo_path).replace("\\", "/")
                    filename = os.path.basename(fpath)

                    try:
                        with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                            orig_content = f.read()

                        modified_content = orig_content
                        file_touched = False

                        for sel, decls in safe_rules.items():
                            # If a specific target stylesheet was identified by the browser for this selector,
                            # ensure we only modify THAT responsible stylesheet!
                            expected_sheet = selector_to_sheet.get(sel)
                            if expected_sheet and expected_sheet != filename and not rel_path.endswith(expected_sheet):
                                continue

                            updated_text, changed = cls.apply_modifications_to_css(modified_content, sel, decls)
                            if changed:
                                modified_content = updated_text
                                file_touched = True

                        if file_touched and modified_content != orig_content:
                            orig_lines = orig_content.splitlines(keepends=True)
                            mod_lines = modified_content.splitlines(keepends=True)

                            unified = list(difflib.unified_diff(
                                orig_lines,
                                mod_lines,
                                fromfile=f"a/{rel_path}",
                                tofile=f"b/{rel_path}"
                            ))

                            if unified:
                                diff_header = f"diff --git a/{rel_path} b/{rel_path}\n"
                                all_diffs.append(diff_header + "".join(unified))
                    except Exception as e:
                        print(f"⚠️ GitDiffPatcher error processing {fpath}: {e}")

        if not all_diffs:
            return None

        full_patch = "".join(all_diffs)

        # Strict validation with git apply --check if repo is a git repository
        is_git_repo = os.path.exists(os.path.join(repo_path, ".git"))
        if is_git_repo:
            try:
                proc = subprocess.run(
                    ["git", "apply", "--check", "--ignore-whitespace"],
                    input=full_patch,
                    text=True,
                    cwd=repo_path,
                    capture_output=True
                )
                if proc.returncode != 0:
                    print(f"❌ Git patch validation failed (git apply --check non-zero): {proc.stderr.strip()}")
                    return None  # Enforce strict rejection of invalid patches!
            except Exception as e:
                print(f"⚠️ Git validation check encountered error: {e}")
                return None

        return full_patch
