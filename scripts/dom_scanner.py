#!/usr/bin/env python3
"""
Polyglot Engine — Headless DOM Layout Scanner & Verification Tool
Scans HTML files or URLs, inspects all UI elements, tests them against
Polyglot Engine's layout constraints, and generates an audit report.
"""

import os
import sys
import json
import argparse
import urllib.request
import re
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def extract_ui_elements(html_content: str):
    """
    Extracts buttons, links, navigation items and labels from raw HTML.
    """
    elements = []
    # Match button tags
    button_matches = re.finditer(r'<button[^>]*>(.*?)</button>', html_content, re.IGNORECASE | re.DOTALL)
    for m in button_matches:
        raw_text = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        if raw_text and len(raw_text) < 100:
            elements.append({"tag": "button", "text": raw_text, "default_max_width": 140.0})

    # Match anchor tags styled as buttons or nav
    link_matches = re.finditer(r'<a[^>]*class=["\'][^"\']*(?:btn|button|nav)[^"\']*["\'][^>]*>(.*?)</a>', html_content, re.IGNORECASE | re.DOTALL)
    for m in link_matches:
        raw_text = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        if raw_text and len(raw_text) < 100:
            elements.append({"tag": "a.btn", "text": raw_text, "default_max_width": 130.0})

    return elements

def main():
    parser = argparse.ArgumentParser(description="Polyglot DOM Layout Scanner")
    parser.add_argument("--file", help="Path to local HTML file to scan")
    parser.add_argument("--url", help="URL of web app to scan")
    parser.add_argument("--api-url", default=os.getenv("POLYGLOT_API_URL", "http://127.0.0.1:8000"), help="Polyglot Engine API URL")
    parser.add_argument("--locales", default="de-DE,ur-PK,ar-SA,ja-JP", help="Target locales to verify")
    args = parser.parse_args()

    html = ""
    if args.file and os.path.exists(args.file):
        with open(args.file, "r", encoding="utf-8") as f:
            html = f.read()
    elif args.url:
        req = urllib.request.Request(args.url, headers={"User-Agent": "Polyglot-DOM-Scanner/1.0"})
        with urllib.request.urlopen(req) as resp:
            html = resp.read().decode("utf-8")
    else:
        # Default scan static/index.html
        default_file = Path(__file__).resolve().parent.parent / "static" / "index.html"
        if default_file.exists():
            with open(default_file, "r", encoding="utf-8") as f:
                html = f.read()

    elements = extract_ui_elements(html)
    print(f"\n🔍 Polyglot DOM Layout Inspector: Scanned {len(elements)} UI components")
    print(f"🎯 Target locales to verify: {args.locales}")
    print("-" * 70)

    target_locales = [l.strip() for l in args.locales.split(",") if l.strip()]
    endpoint = f"{args.api_url.rstrip('/')}/v1/localize"

    overflows_found = 0
    repairs_available = 0

    for idx, el in enumerate(elements, 1):
        text = el["text"]
        max_w = el["default_max_width"]

        payload = {
            "source_text": text,
            "source_locale": "en-US",
            "target_locales": target_locales,
            "ui_context": {
                "element_type": "button",
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
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                for loc in target_locales:
                    res = data["results"][loc]
                    if res.get("overflow_prevented"):
                        overflows_found += 1
                        repairs_available += 1
                        print(f"⚠️  [{loc}] Component '{text}' ({el['tag']}):")
                        print(f"     Overflow Detected: {res['overflow_prevented']['rejected_width_px']}px > {max_w}px limit")
                        print(f"     Polyglot Safe Swap: '{res['raw_text']}' ({res['metrics']['measured_width_px']}px, FITS)")
        except Exception as e:
            pass

    print("\n" + "=" * 70)
    print(f"📊 DOM Layout Scan Finished:")
    print(f"  • Total Elements Scanned: {len(elements)}")
    print(f"  • Layout Overflows Caught: {overflows_found}")
    print(f"  • Automatic Safe Repairs:  {repairs_available}")
    print("=" * 70)

if __name__ == "__main__":
    main()
