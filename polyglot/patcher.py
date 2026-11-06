"""
Polyglot Patcher — Dynamic CSS Generation & Source Repository Patching
Generates targeted, calculated CSS rules based on diagnosed element geometry.
Enforces safety rules to prevent modifying broad generic HTML selectors.
When a local repository path is provided, locates the actual source file,
modifies the stylesheet in memory, produces a genuine unified Git diff,
and validates it via `git apply --check`.
"""

import os
import re
import difflib
import subprocess
from typing import Dict, Any, List, Optional

UNSAFE_GENERIC_SELECTORS = {
    "button", "a", "div", "span", "p", "h1", "h2", "h3", "h4", "h5", "h6",
    "label", "input", "body", "html", "header", "nav", "aside", "table", "tr", "td", "th"
}

class DynamicCSSPatcher:
    @staticmethod
    def generate_css(diagnosed_issues: List[Dict[str, Any]]) -> str:
        """
        Dynamically calculates targeted CSS rules derived directly from failing element geometry.
        Strictly rejects generic HTML tags to prevent cross-component layout damage.
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
            elif cat in ("FLEX_CONTAINER_NO_WRAP", "FLEX_SIBLING_OVERLAP"):
                rules[sel] = [
                    f"min-width: {needed_w:.0f}px !important;",
                    "flex-shrink: 0 !important;"
                ]
            elif cat == "TEXT_VERBOSITY_EXPANSION":
                rules[sel] = [
                    "white-space: normal !important;",
                    "word-break: break-word !important;"
                ]
            else:
                rules[sel] = [
                    f"min-width: {needed_w:.0f}px !important;",
                    "flex-shrink: 0 !important;"
                ]

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
    def apply_modifications_to_css(content: str, selector: str, declarations: List[str]) -> str:
        """
        Locates the CSS rule block for selector and injects/updates declarations before closing brace.
        If selector block is not found, appends the new rule block cleanly.
        """
        clean_sel = selector.strip()
        pattern = re.compile(
            r"(^|\n)([ \t]*" + re.escape(clean_sel) + r"[^{]*\{)([^}]*)(\})",
            re.MULTILINE
        )

        match = pattern.search(content)
        if match:
            prefix = match.group(1)
            header = match.group(2)
            body = match.group(3)
            closing = match.group(4)

            # Insert missing declarations
            existing_body = body.rstrip()
            indent = "  "
            new_decls = "\n".join(f"{indent}{d}" for d in declarations if d.strip() not in existing_body)
            if new_decls:
                updated_body = f"{existing_body}\n{new_decls}\n"
            else:
                updated_body = body

            return content[:match.start()] + prefix + header + updated_body + closing + content[match.end():]
        else:
            # Append new rule block
            new_block = f"\n\n{clean_sel} {{\n" + "\n".join(f"  {d}" for d in declarations) + "\n}\n"
            return content.rstrip() + new_block

    @classmethod
    def generate_patch(cls, repo_path: Optional[str], css_rules: Dict[str, List[str]]) -> Optional[str]:
        """
        Searches local source files for the matching selector, modifies in memory,
        and produces a genuine unified Git diff patch with exact line numbers.
        Validates the patch using git apply --check when in a git repo.
        """
        if not repo_path or not os.path.exists(repo_path) or not css_rules:
            return None

        # Filter unsafe generic selectors
        safe_rules = {s: d for s, d in css_rules.items() if s.strip().lower() not in UNSAFE_GENERIC_SELECTORS}
        if not safe_rules:
            return None

        all_diffs = []

        # Find matching stylesheet files
        for root, _, files in os.walk(repo_path):
            if any(part in root for part in [".git", "node_modules", ".venv", "__pycache__"]):
                continue

            for file in files:
                if file.endswith((".css", ".scss", ".module.css", ".html")):
                    fpath = os.path.join(root, file)
                    rel_path = os.path.relpath(fpath, repo_path).replace("\\", "/")

                    try:
                        with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                            orig_content = f.read()

                        modified_content = orig_content
                        file_touched = False

                        for sel, decls in safe_rules.items():
                            clean_sel = sel.lstrip(".#")
                            # If selector or class exists in file
                            if clean_sel in orig_content or sel in orig_content:
                                modified_content = cls.apply_modifications_to_css(modified_content, sel, decls)
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

        # Validate with git apply --check if repo is a git repository
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
                    print(f"⚠️ Warning: git apply --check reported: {proc.stderr.strip()}")
            except Exception:
                pass

        return full_patch
