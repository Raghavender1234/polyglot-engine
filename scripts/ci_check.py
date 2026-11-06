#!/usr/bin/env python3
"""
Polyglot Engine CI/CD Pipeline Script
Usage:
    python scripts/ci_check.py --input locales/en.json --targets de-DE,ur-PK,ar-SA,ja-JP --api-url https://polyglot-engine.onrender.com
"""

import os
import sys
import json
import argparse
import urllib.request
import urllib.error

if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def main():
    parser = argparse.ArgumentParser(description="Polyglot CI/CD Localization & Layout Checker")
    parser.add_argument("--input", default="locales/en.json", help="Path to source en.json")
    parser.add_argument("--targets", default="de-DE,ur-PK,ar-SA,ja-JP", help="Comma-separated target locales")
    parser.add_argument("--api-url", default=os.getenv("POLYGLOT_API_URL", "http://127.0.0.1:8000"), help="Polyglot Engine API URL")
    parser.add_argument("--api-key", default=os.getenv("POLYGLOT_API_KEY", "test_key_polyglot_123"), help="Polyglot API Key")
    parser.add_argument("--max-width", type=float, default=145.0, help="Default container max width for button/CTA keys")
    args = parser.parse_args()

    input_path = args.input
    if not os.path.exists(input_path):
        # Create a sample en.json if none exists
        os.makedirs(os.path.dirname(input_path) or ".", exist_ok=True)
        sample = {
            "checkout_button": "Complete Purchase - $49.99",
            "subscribe_cta": "Subscribe to Pro (Annual)",
            "sign_in": "Sign in with Google Account"
        }
        with open(input_path, "w", encoding="utf-8") as f:
            json.dump(sample, f, indent=2)
        print(f"Created sample input file at {input_path}")

    with open(input_path, "r", encoding="utf-8") as f:
        source_dict = json.load(f)

    target_locales = [t.strip() for t in args.targets.split(",") if t.strip()]
    output_bundles = {loc: {} for loc in target_locales}
    overflow_warnings = []

    print(f"\n🚀 Running Polyglot CI/CD Check against: {args.api_url}")
    print(f"📄 Source strings: {len(source_dict)} | Target locales: {target_locales}\n" + "-" * 70)

    endpoint = f"{args.api_url.rstrip('/')}/v1/localize"

    for key, text in source_dict.items():
        payload = {
            "source_text": text,
            "source_locale": "en-US",
            "target_locales": target_locales,
            "ui_context": {
                "element_type": "button",
                "max_width_px": args.max_width,
                "font_size_px": 14.0,
                "font_weight": 400
            }
        }
        req_data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            endpoint,
            data=req_data,
            headers={
                "Content-Type": "application/json",
                "X-API-Key": args.api_key
            }
        )

        try:
            with urllib.request.urlopen(req) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                for loc in target_locales:
                    loc_res = res["results"][loc]
                    output_bundles[loc][key] = loc_res["ui_safe_text"]
                    
                    if loc_res.get("overflow_prevented"):
                        overflow_warnings.append({
                            "key": key,
                            "locale": loc,
                            "rejected": loc_res["overflow_prevented"]["rejected_full_text"],
                            "rejected_width": loc_res["overflow_prevented"]["rejected_width_px"],
                            "used": loc_res["raw_text"],
                            "used_width": loc_res["metrics"]["measured_width_px"]
                        })
        except urllib.error.HTTPError as e:
            print(f"❌ API Error for key '{key}': HTTP {e.code} - {e.read().decode('utf-8')}")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Connection Error for key '{key}': {e}")
            sys.exit(1)

    # Write localized JSON files
    base_dir = os.path.dirname(input_path) or "."
    for loc, bundle in output_bundles.items():
        out_file = os.path.join(base_dir, f"{loc}.json")
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(bundle, f, ensure_ascii=False, indent=2)
        print(f"✅ Generated: {out_file} ({len(bundle)} keys)")

    # Print Summary Report
    print("\n" + "=" * 70)
    print("📊 POLYGLOT LAYOUT SAFETY REPORT")
    print("=" * 70)
    if overflow_warnings:
        print(f"⚠️  {len(overflow_warnings)} UI Overflows Prevented Automatically:")
        for w in overflow_warnings:
            diff = round(w["rejected_width"] - args.max_width, 1)
            print(f"  • [{w['locale']}] Key '{w['key']}':")
            print(f"      Rejected: \"{w['rejected']}\" ({w['rejected_width']}px, +{diff}px OVERFLOW)")
            print(f"      Swapped:  \"{w['used']}\" ({w['used_width']}px, SAFE)")
    else:
        print("✅ All strings fit within container constraints naturally.")
    print("=" * 70)

if __name__ == "__main__":
    main()
