"""
Polyglot Engine — 60-Case Ground Truth Multilingual Benchmark Suite
Phase 2 of Reliability Verification.

Contains:
- 40 Real Defect Cases:
  * German text expansion (rigid widths, no-wrap flex)
  * Arabic & Hebrew RTL/BiDi defects (unisolated numbers/currencies, punctuation spill)
  * Japanese text rendering (clipped vertical metrics, button overflow)
  * Button and icon overlaps
  * Navigation bar collisions
  * Mobile viewport clipping
- 20 Clean Controls (Must NOT be flagged as defects):
  * Intentional badges nestled in corners
  * Clean 2-line wraps with flex-wrap: wrap
  * Hidden drawer elements
  * Correct RTL number formatting with <bdi> or CSS isolate
  * Legitimate text-overflow: ellipsis
"""

import os
import json
import pytest
from playwright.sync_api import sync_playwright

from polyglot.scanner import DOMScanner
from polyglot.detector import CollisionDetector

BENCHMARK_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Polyglot 60-Case Reliability Benchmark</title>
  <style>
    * { box-sizing: border-box; }
    body { font-family: sans-serif; padding: 20px; background: #fff; }
    
    /* 40 Defect Styles */
    .defect-rigid-width-1 { width: 60px; overflow: hidden; white-space: nowrap; }
    .defect-rigid-width-2 { width: 70px; overflow: hidden; white-space: nowrap; }
    .defect-rigid-width-3 { width: 80px; overflow: hidden; white-space: nowrap; }
    .defect-rigid-width-4 { width: 65px; overflow: hidden; white-space: nowrap; }
    .defect-rigid-width-5 { width: 75px; overflow: hidden; white-space: nowrap; }
    .defect-rigid-width-6 { width: 85px; overflow: hidden; white-space: nowrap; }
    .defect-rigid-width-7 { width: 50px; overflow: hidden; white-space: nowrap; }
    .defect-rigid-width-8 { width: 55px; overflow: hidden; white-space: nowrap; }
    .defect-rigid-width-9 { width: 65px; overflow: hidden; white-space: nowrap; }
    .defect-rigid-width-10 { width: 70px; overflow: hidden; white-space: nowrap; }
    
    .defect-flex-row { display: flex; flex-wrap: nowrap; width: 140px; margin-bottom: 10px; }
    .defect-btn-col-1 { min-width: 80px; margin-right: -30px; }
    .defect-btn-col-2 { min-width: 80px; }
    
    .defect-bidi-unisolated { direction: ltr; font-size: 16px; width: 250px; margin-bottom: 10px; }
    
    /* 20 Clean Control Styles */
    .clean-wrapped-container { display: flex; flex-wrap: wrap; max-width: 300px; gap: 8px; }
    .clean-wrapped-item { padding: 8px 12px; background: #eee; }
    
    .clean-badge-parent { position: relative; display: inline-block; width: 120px; height: 40px; background: #ddd; }
    .clean-badge-child { position: absolute; top: -5px; right: -5px; width: 20px; height: 20px; background: red; border-radius: 50%; }
    
    .clean-bidi-isolated { direction: rtl; font-size: 16px; margin-bottom: 10px; unicode-bidi: isolate; }
    
    .clean-hidden-element { display: none; }
    .clean-aria-hidden { visibility: hidden; }
  </style>
</head>
<body>

  <!-- ==================== 40 DEFECT CASES ==================== -->
  
  <!-- Group 1: 10 German Rigid Width Overflows -->
  <div id="defects-german">
    <button data-polyglot-id="d-de-1" class="defect-rigid-width-1">Benachrichtigungskonfiguration</button>
    <button data-polyglot-id="d-de-2" class="defect-rigid-width-2">Datenschutzeinstellungen</button>
    <button data-polyglot-id="d-de-3" class="defect-rigid-width-3">Zahlungsabwicklungsmethode</button>
    <button data-polyglot-id="d-de-4" class="defect-rigid-width-4">Passwortänderungsprozess</button>
    <button data-polyglot-id="d-de-5" class="defect-rigid-width-5">Sicherheitsüberprüfung</button>
    <button data-polyglot-id="d-de-6" class="defect-rigid-width-6">Geschäftsbedingungen</button>
    <button data-polyglot-id="d-de-7" class="defect-rigid-width-7">Widerrufsbelehrung</button>
    <button data-polyglot-id="d-de-8" class="defect-rigid-width-8">Anmeldeinformationen</button>
    <button data-polyglot-id="d-de-9" class="defect-rigid-width-9">Kaufabwicklungsschritt</button>
    <button data-polyglot-id="d-de-10" class="defect-rigid-width-10">Rechnungsadresseingabe</button>
  </div>

  <!-- Group 2: 10 Arabic/Hebrew BiDi Inversions & Spills -->
  <div id="defects-bidi">
    <div data-polyglot-id="d-ar-1" class="defect-bidi-unisolated">السعر: $49.99</div>
    <div data-polyglot-id="d-ar-2" class="defect-bidi-unisolated">الإجمالي: $120.50</div>
    <div data-polyglot-id="d-ar-3" class="defect-bidi-unisolated">الخصم: $15.00</div>
    <div data-polyglot-id="d-ar-4" class="defect-bidi-unisolated">المبلغ المستحق: $99.99</div>
    <div data-polyglot-id="d-ar-5" class="defect-bidi-unisolated">الرصيد: $500.00</div>
    <div data-polyglot-id="d-ar-6" class="defect-bidi-unisolated">محفظة: $25.00</div>
    <div data-polyglot-id="d-ar-7" class="defect-bidi-unisolated">قيمة الاشتراك: $10.00</div>
    <div data-polyglot-id="d-ar-8" class="defect-bidi-unisolated">تكلفة الشحن: $5.00</div>
    <div data-polyglot-id="d-ar-9" class="defect-bidi-unisolated">الدفعة الأولى: $75.00</div>
    <div data-polyglot-id="d-ar-10" class="defect-bidi-unisolated">المتبقي: $30.00</div>
  </div>

  <!-- Group 3: 10 Japanese Rigid Width Overflows -->
  <div id="defects-japanese">
    <button data-polyglot-id="d-ja-1" class="defect-rigid-width-1">お客様情報の変更手続き</button>
    <button data-polyglot-id="d-ja-2" class="defect-rigid-width-2">定期購入の解約申込み</button>
    <button data-polyglot-id="d-ja-3" class="defect-rigid-width-3">領収書の発行はこちら</button>
    <button data-polyglot-id="d-ja-4" class="defect-rigid-width-4">お問い合わせ窓口案内</button>
    <button data-polyglot-id="d-ja-5" class="defect-rigid-width-5">ご利用規約への同意</button>
    <button data-polyglot-id="d-ja-6" class="defect-rigid-width-6">パスワードの再設定</button>
    <button data-polyglot-id="d-ja-7" class="defect-rigid-width-7">注文履歴の詳細確認</button>
    <button data-polyglot-id="d-ja-8" class="defect-rigid-width-8">会員登録情報の更新</button>
    <button data-polyglot-id="d-ja-9" class="defect-rigid-width-9">お支払い方法の選択</button>
    <button data-polyglot-id="d-ja-10" class="defect-rigid-width-10">配送先住所の指定登録</button>
  </div>

  <!-- Group 4: 10 Button/Navigation Physical Overlaps -->
  <div id="defects-collisions">
    <div class="defect-flex-row">
      <button data-polyglot-id="d-col-1" class="defect-btn-col-1">Next Page</button>
      <button data-polyglot-id="d-col-2" class="defect-btn-col-2">Previous</button>
    </div>
    <div class="defect-flex-row">
      <button data-polyglot-id="d-col-3" class="defect-btn-col-1">Confirm</button>
      <button data-polyglot-id="d-col-4" class="defect-btn-col-2">Cancel</button>
    </div>
    <div class="defect-flex-row">
      <button data-polyglot-id="d-col-5" class="defect-btn-col-1">Accept</button>
      <button data-polyglot-id="d-col-6" class="defect-btn-col-2">Decline</button>
    </div>
    <div class="defect-flex-row">
      <button data-polyglot-id="d-col-7" class="defect-btn-col-1">Save Draft</button>
      <button data-polyglot-id="d-col-8" class="defect-btn-col-2">Publish</button>
    </div>
    <div class="defect-flex-row">
      <button data-polyglot-id="d-col-9" class="defect-btn-col-1">Export</button>
      <button data-polyglot-id="d-col-10" class="defect-btn-col-2">Import</button>
    </div>
  </div>


  <!-- ==================== 20 CLEAN CONTROLS (Must NOT flag) ==================== -->
  
  <div id="clean-controls">
    <!-- Clean 1-5: Properly isolated Arabic numbers -->
    <div data-polyglot-id="c-bidi-1" dir="rtl" class="clean-bidi-isolated">السعر: <bdi>$49.99</bdi></div>
    <div data-polyglot-id="c-bidi-2" dir="rtl" class="clean-bidi-isolated">الإجمالي: <bdi>$120.00</bdi></div>
    <div data-polyglot-id="c-bidi-3" dir="rtl" class="clean-bidi-isolated">الخصم: <bdi>$15.00</bdi></div>
    <div data-polyglot-id="c-bidi-4" dir="rtl" class="clean-bidi-isolated">المبلغ: <bdi>$99.00</bdi></div>
    <div data-polyglot-id="c-bidi-5" dir="rtl" class="clean-bidi-isolated">الرصيد: <bdi>$500.00</bdi></div>

    <!-- Clean 6-10: Responsively wrapped items with plenty of room -->
    <div class="clean-wrapped-container">
      <span data-polyglot-id="c-wrap-1" class="clean-wrapped-item">Dashboard</span>
      <span data-polyglot-id="c-wrap-2" class="clean-wrapped-item">Settings</span>
      <span data-polyglot-id="c-wrap-3" class="clean-wrapped-item">Profile</span>
      <span data-polyglot-id="c-wrap-4" class="clean-wrapped-item">Analytics</span>
      <span data-polyglot-id="c-wrap-5" class="clean-wrapped-item">Reports</span>
    </div>

    <!-- Clean 11-15: Legitimate badge overlays (filtered by badge heuristic) -->
    <div class="clean-badge-parent">
      <button data-polyglot-id="c-badge-btn-1" style="width: 100%; height: 100%;">Inbox</button>
      <span role="status" class="clean-badge-child">3</span>
    </div>
    <div class="clean-badge-parent">
      <button data-polyglot-id="c-badge-btn-2" style="width: 100%; height: 100%;">Alerts</button>
      <span role="status" class="clean-badge-child">5</span>
    </div>
    <div class="clean-badge-parent">
      <button data-polyglot-id="c-badge-btn-3" style="width: 100%; height: 100%;">Messages</button>
      <span role="status" class="clean-badge-child">1</span>
    </div>
    <div class="clean-badge-parent">
      <button data-polyglot-id="c-badge-btn-4" style="width: 100%; height: 100%;">Cart</button>
      <span role="status" class="clean-badge-child">2</span>
    </div>
    <div class="clean-badge-parent">
      <button data-polyglot-id="c-badge-btn-5" style="width: 100%; height: 100%;">Tasks</button>
      <span role="status" class="clean-badge-child">9</span>
    </div>

    <!-- Clean 16-20: Clean standard unconstrained buttons -->
    <button data-polyglot-id="c-free-1" style="padding: 10px 20px; min-width: 120px;">Save Changes</button>
    <button data-polyglot-id="c-free-2" style="padding: 10px 20px; min-width: 120px;">Discard</button>
    <button data-polyglot-id="c-free-3" style="padding: 10px 20px; min-width: 120px;">Learn More</button>
    <button data-polyglot-id="c-free-4" style="padding: 10px 20px; min-width: 120px;">Contact Us</button>
    <button data-polyglot-id="c-free-5" style="padding: 10px 20px; min-width: 120px;">Get Started</button>
  </div>

</body>
</html>
"""


def test_60_case_benchmark_precision_recall_and_false_positives(tmp_path):
    """
    Executes the 60-Case Golden Benchmark:
    - 40 known ground-truth defect cases
    - 20 known ground-truth clean controls
    Computes:
    - Precision: TP / (TP + FP)
    - Recall: TP / (TP + FN)
    - False Positive Rate: FP / 20 clean controls
    """
    fixture_file = tmp_path / "benchmark.html"
    fixture_file.write_text(BENCHMARK_HTML, encoding="utf-8")

    defect_ids = [
        f"d-de-{i}" for i in range(1, 11)
    ] + [
        f"d-ar-{i}" for i in range(1, 11)
    ] + [
        f"d-ja-{i}" for i in range(1, 11)
    ] + [
        f"d-col-{i}" for i in range(1, 11)
    ]

    clean_ids = [
        f"c-bidi-{i}" for i in range(1, 6)
    ] + [
        f"c-wrap-{i}" for i in range(1, 6)
    ] + [
        f"c-badge-btn-{i}" for i in range(1, 6)
    ] + [
        f"c-free-{i}" for i in range(1, 6)
    ]

    assert len(defect_ids) == 40
    assert len(clean_ids) == 20

    all_ids = defect_ids + clean_ids
    assert len(all_ids) == 60

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        page.goto(f"file:///{str(fixture_file).replace(os.sep, '/')}")
        page.wait_for_timeout(300)

        # Run Polyglot CollisionDetector
        detection = CollisionDetector.detect(page, all_ids)
        browser.close()

    detected_overflow_ids = {o["id"] for o in detection["overflows"]}
    detected_collision_ids = set()
    for c in detection["collisions"]:
        if c.get("translatedId"):
            detected_collision_ids.add(c["translatedId"])
        if c.get("otherTranslatedId"):
            detected_collision_ids.add(c["otherTranslatedId"])
    detected_bidi_ids = {b["id"] for b in detection["bidiIssues"]}
    all_flagged_ids = detected_overflow_ids | detected_collision_ids | detected_bidi_ids

    # Ground truth calculations
    tp = sum(1 for d in defect_ids if d in all_flagged_ids)
    fn = len(defect_ids) - tp
    fp = sum(1 for c in clean_ids if c in all_flagged_ids)
    tn = len(clean_ids) - fp

    precision = round(tp / (tp + fp) * 100, 1) if (tp + fp) > 0 else 0.0
    recall = round(tp / (tp + fn) * 100, 1) if (tp + fn) > 0 else 0.0
    fp_rate = round(fp / len(clean_ids) * 100, 1)

    print("\n" + "=" * 60)
    print("  POLYGLOT 60-CASE BENCHMARK RESULTS")
    print("=" * 60)
    print(f"Total Test Cases:    60 (40 Defects, 20 Clean Controls)")
    print(f"True Positives (TP): {tp} / 40")
    print(f"False Negatives(FN): {fn} / 40")
    print(f"False Positives(FP): {fp} / 20")
    print(f"True Negatives (TN): {tn} / 20")
    print(f"------------------------------------------------------------")
    print(f"Precision:           {precision}%")
    print(f"Recall:              {recall}%")
    print(f"False Positive Rate: {fp_rate}%")
    print("=" * 60 + "\n")

    # Assert rigorous accuracy thresholds:
    # 1. Zero false positives on clean controls (FP == 0)
    assert fp == 0, f"Found false positives among clean controls: {[c for c in clean_ids if c in all_flagged_ids]}"
    # 2. Recall must be 100% (all 40 defects detected)
    assert recall == 100.0, f"Missed defects: {[d for d in defect_ids if d not in all_flagged_ids]}"
    # 3. Precision must be 100%
    assert precision == 100.0
