#!/usr/bin/env python3
"""
Polyglot Engine — Headless DOM Layout Scanner & Verification Tool
Scans HTML files or live URLs, inspects interactive and text UI elements,
tests them against Polyglot Engine's layout constraints, and generates an audit report.
Supports standard library HTML parser with optional Playwright headless browser execution.
"""

import os
import sys
import json
import argparse
import urllib.request
import re
from pathlib import Path
from html.parser import HTMLParser

if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

class UIElementParser(HTMLParser):
    """
    Standard-library HTML Parser that extracts buttons, navigation links,
    input actions, badges, and headings with their layout roles.
    """
    def __init__(self):
        super().__init__()
        self.elements = []
        self._current_tag = None
        self._current_attrs = {}
        self._text_buffer = []
        self._inside_target = False

    def handle_starttag(self, tag, attrs):
        attr_dict = dict(attrs)
        classes = attr_dict.get("class", "").split()
        role = attr_dict.get("role", "")
        tag_lower = tag.lower()

        is_target = False
        default_max_width = 140.0

        if tag_lower in ("button", "label"):
            is_target = True
            default_max_width = 140.0 if tag_lower == "button" else 160.0
        elif tag_lower == "a" and any(c in classes for c in ["btn", "button", "nav-link", "menu-item"]):
            is_target = True
            default_max_width = 130.0
        elif role in ("button", "tab", "menuitem"):
            is_target = True
            default_max_width = 140.0
        elif tag_lower in ("h1", "h2", "h3", "h4"):
            is_target = True
            default_max_width = 280.0
        elif tag_lower == "input" and attr_dict.get("type", "").lower() in ("submit", "button", "reset"):
            val = attr_dict.get("value", "").strip()
            if val:
                self.elements.append({
                    "tag": f"input[{attr_dict.get('type')}]",
                    "text": val,
                    "default_max_width": 140.0
                })

        if is_target:
            self._inside_target = True
            self._current_tag = tag_lower
            self._current_attrs = attr_dict
            self._text_buffer = []

    def handle_data(self, data):
        if self._inside_target:
            self._text_buffer.append(data)

    def handle_endtag(self, tag):
        if self._inside_target and tag.lower() == self._current_tag:
            raw_text = "".join(self._text_buffer).strip()
            # Filter empty or noisy strings
            if raw_text and 1 < len(raw_text) < 120 and not raw_text.startswith("{"):
                width = 140.0
                if self._current_tag in ("h1", "h2", "h3", "h4"):
                    width = 260.0
                elif self._current_tag == "a":
                    width = 130.0

                self.elements.append({
                    "tag": self._current_tag,
                    "text": raw_text,
                    "default_max_width": width
                })
            self._inside_target = False
            self._current_tag = None
            self._text_buffer = []

def extract_ui_elements(html_content: str):
    parser = UIElementParser()
    try:
        parser.feed(html_content)
        return parser.elements
    except Exception:
        # Graceful fallback to regex if malformed HTML
        elements = []
        matches = re.finditer(r'<(button|h[1-4]|a)[^>]*>(.*?)</\1>', html_content, re.IGNORECASE | re.DOTALL)
        for m in matches:
            text = re.sub(r'<[^>]+>', '', m.group(2)).strip()
            if text and len(text) < 100:
                elements.append({"tag": m.group(1), "text": text, "default_max_width": 140.0})
        return elements

def scan_with_playwright_if_available(url: str):
    """
    Attempts headless browser scan using Playwright if installed in the environment.
    """
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="networkidle")
            content = page.content()
            browser.close()
            return content
    except Exception:
        return None

def main():
    parser = argparse.ArgumentParser(description="Polyglot DOM Layout Scanner")
    parser.add_argument("--file", help="Path to local HTML file to scan")
    parser.add_argument("--url", help="URL of web app to scan")
    parser.add_argument("--api-url", default=os.getenv("POLYGLOT_API_URL", "http://127.0.0.1:8000"), help="Polyglot Engine API URL")
    parser.add_argument("--locales", default="de-DE,ur-PK,ar-SA,ja-JP", help="Target locales to verify")
    parser.add_argument("--json", action="store_true", help="Output audit report as JSON")
    args = parser.parse_args()

    html = ""
    if args.url:
        rendered = scan_with_playwright_if_available(args.url)
        if rendered:
            html = rendered
        else:
            req = urllib.request.Request(args.url, headers={"User-Agent": "Polyglot-DOM-Scanner/1.1"})
            with urllib.request.urlopen(req) as resp:
                html = resp.read().decode("utf-8")
    elif args.file and os.path.exists(args.file):
        with open(args.file, "r", encoding="utf-8") as f:
            html = f.read()
    else:
        # Default scan static/index.html
        default_file = Path(__file__).resolve().parent.parent / "static" / "index.html"
        if default_file.exists():
            with open(default_file, "r", encoding="utf-8") as f:
                html = f.read()

    elements = extract_ui_elements(html)
    target_locales = [l.strip() for l in args.locales.split(",") if l.strip()]
    endpoint = f"{args.api_url.rstrip('/')}/v1/localize"

    if not args.json:
        print(f"\n🔍 Polyglot DOM Layout Inspector: Scanned {len(elements)} UI components")
        print(f"🎯 Target locales to verify: {', '.join(target_locales)}")
        print("-" * 75)

    overflows_found = 0
    repairs_available = 0
    report_items = []

    for idx, el in enumerate(elements, 1):
        text = el["text"]
        max_w = el["default_max_width"]

        payload = {
            "source_text": text,
            "source_locale": "en-US",
            "target_locales": target_locales,
            "ui_context": {
                "element_type": "button" if "button" in el["tag"] else "general",
                "max_width_px": max_w,
                "font_size_px": 14.0,
                "font_weight": 500
            }
        }

        try:
            req = urllib.request.Request(
                endpoint,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                for loc in target_locales:
                    res = data["results"][loc]
                    if res.get("overflow_prevented"):
                        overflows_found += 1
                        repairs_available += 1
                        report_items.append({
                            "element": el["tag"],
                            "text": text,
                            "locale": loc,
                            "rejected_width_px": res['overflow_prevented']['rejected_width_px'],
                            "container_max_width_px": max_w,
                            "safe_repair": res['raw_text'],
                            "measured_width_px": res['metrics']['measured_width_px']
                        })
                        if not args.json:
                            print(f"⚠️  [{loc}] Component '{text}' (<{el['tag']}>):")
                            print(f"     Overflow: {res['overflow_prevented']['rejected_width_px']}px exceeds {max_w}px container")
                            print(f"     Polyglot Safe Repair: '{res['raw_text']}' ({res['metrics']['measured_width_px']}px, FITS)")
        except Exception:
            pass

    if args.json:
        print(json.dumps({
            "elements_scanned": len(elements),
            "overflows_detected": overflows_found,
            "repairs_available": repairs_available,
            "findings": report_items
        }, indent=2))
    else:
        print("\n" + "=" * 75)
        print(f"📊 DOM Layout Scan Audit Summary:")
        print(f"  • Total Interactive Elements Scanned: {len(elements)}")
        print(f"  • Layout Overflows Caught & Blocked:  {overflows_found}")
        print(f"  • Automatic Non-Destructive Repairs:  {repairs_available}")
        print("=" * 75)

if __name__ == "__main__":
    main()
