"""Standalone Benchmark Harness for Moondream 2 Visual Multilingual Defect Detection.

This experiment evaluates whether a small vision model (Moondream 2) can
accurately distinguish visually defective multilingual UI components from clean controls,
without relying on pixel diffing or altering core Polyglot engine code.

Benchmark suite:
- 50 labelled test cases:
    - 25 positive defects: text clipping, font overflow, icon overlap, BiDi punctuation displacement.
    - 25 negative controls: valid tight margins, correct BiDi numerals/currencies,
      Japanese/Hindi rendering, valid multiline wraps, pill badges.
- Evaluates precision, recall, false positive rate, latency, and memory usage.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class TestCase:
    id: str
    locale: str
    category: str
    is_defect_ground_truth: bool
    expected_defect_type: Optional[str]
    description: str
    html_snippet: str
    css_rules: str
    target_selector: str


BENCHMARK_CASES: List[TestCase] = [
    # --- POSITIVE DEFECTS: CLIPPING & OVERFLOW (10 cases) ---
    TestCase(
        id="clip_de_btn_overflow",
        locale="de",
        category="clipping",
        is_defect_ground_truth=True,
        expected_defect_type="text_clipped",
        description="German compound word clipped by fixed width container with overflow hidden",
        html_snippet='<button id="target" class="btn">Benutzerkontoeinstellungen</button>',
        css_rules=".btn { width: 140px; height: 38px; overflow: hidden; white-space: nowrap; font-size: 14px; text-overflow: clip; background: #2563eb; color: #fff; border: none; border-radius: 4px; padding: 0 8px; }",
        target_selector="#target"
    ),
    TestCase(
        id="clip_fi_dialog_title",
        locale="fi",
        category="clipping",
        is_defect_ground_truth=True,
        expected_defect_type="text_clipped",
        description="Finnish agglutinative heading truncated inside modal card",
        html_snippet='<div id="target" class="title">Järjestelmäasetusvalikko</div>',
        css_rules=".title { width: 160px; height: 26px; overflow: hidden; white-space: nowrap; font-size: 16px; font-weight: bold; color: #111; }",
        target_selector="#target"
    ),
    TestCase(
        id="clip_ru_action_btn",
        locale="ru",
        category="clipping",
        is_defect_ground_truth=True,
        expected_defect_type="text_clipped",
        description="Russian action button text cut in half horizontally by tight max-height",
        html_snippet='<button id="target" class="btn">Зарегистрироваться</button>',
        css_rules=".btn { width: 150px; height: 22px; overflow: hidden; line-height: 18px; font-size: 15px; background: #059669; color: #fff; border: none; }",
        target_selector="#target"
    ),
    TestCase(
        id="clip_fr_submit_ellipsis",
        locale="fr",
        category="clipping",
        is_defect_ground_truth=True,
        expected_defect_type="text_clipped",
        description="French submit button truncated prematurely with ugly clipping",
        html_snippet='<button id="target" class="btn">Télécharger le document</button>',
        css_rules=".btn { width: 120px; height: 36px; overflow: hidden; white-space: nowrap; font-size: 14px; background: #4f46e5; color: #fff; }",
        target_selector="#target"
    ),
    TestCase(
        id="clip_pl_tab_label",
        locale="pl",
        category="clipping",
        is_defect_ground_truth=True,
        expected_defect_type="text_clipped",
        description="Polish navigation tab label cut off at end",
        html_snippet='<div id="target" class="tab">Szczegółowe podsumowanie</div>',
        css_rules=".tab { width: 130px; height: 30px; overflow: hidden; white-space: nowrap; font-size: 13px; border-bottom: 2px solid #2563eb; }",
        target_selector="#target"
    ),
    TestCase(
        id="clip_de_descender",
        locale="de",
        category="clipping",
        is_defect_ground_truth=True,
        expected_defect_type="text_clipped",
        description="German text with descenders (g, y, p) clipped vertically at baseline",
        html_snippet='<div id="target" class="badge">Typologieprüfung</div>',
        css_rules=".badge { width: 180px; height: 15px; overflow: hidden; line-height: 14px; font-size: 14px; background: #fef08a; color: #854d0e; }",
        target_selector="#target"
    ),
    TestCase(
        id="clip_es_card_footer",
        locale="es",
        category="clipping",
        is_defect_ground_truth=True,
        expected_defect_type="text_clipped",
        description="Spanish confirmation notice truncated in card footer",
        html_snippet='<div id="target" class="notice">Confirmación de transferencia bancaria</div>',
        css_rules=".notice { width: 180px; height: 20px; overflow: hidden; white-space: nowrap; font-size: 13px; color: #374151; }",
        target_selector="#target"
    ),
    TestCase(
        id="clip_it_pill_filter",
        locale="it",
        category="clipping",
        is_defect_ground_truth=True,
        expected_defect_type="text_clipped",
        description="Italian filter pill tag clipping end characters",
        html_snippet='<span id="target" class="pill">Visualizzazione avanzata</span>',
        css_rules=".pill { display: inline-block; width: 120px; height: 26px; overflow: hidden; white-space: nowrap; font-size: 12px; border-radius: 9999px; background: #e0e7ff; padding: 4px 6px; }",
        target_selector="#target"
    ),
    TestCase(
        id="clip_el_greek_btn",
        locale="el",
        category="clipping",
        is_defect_ground_truth=True,
        expected_defect_type="text_clipped",
        description="Greek letters overflowing card boundaries",
        html_snippet='<button id="target" class="btn">Επεξεργασία προφίλ χρήστη</button>',
        css_rules=".btn { width: 130px; height: 34px; overflow: hidden; white-space: nowrap; font-size: 13px; background: #dc2626; color: #fff; }",
        target_selector="#target"
    ),
    TestCase(
        id="clip_nl_sidebar_item",
        locale="nl",
        category="clipping",
        is_defect_ground_truth=True,
        expected_defect_type="text_clipped",
        description="Dutch navigation item overflowing sidebar slot",
        html_snippet='<a id="target" class="nav">Gebruikersovereenkomst</a>',
        css_rules=".nav { display: block; width: 110px; height: 24px; overflow: hidden; white-space: nowrap; font-size: 13px; color: #1e40af; }",
        target_selector="#target"
    ),

    # --- POSITIVE DEFECTS: TEXT-ICON COLLISION & OVERLAP (8 cases) ---
    TestCase(
        id="overlap_de_icon_btn",
        locale="de",
        category="text_icon_overlap",
        is_defect_ground_truth=True,
        expected_defect_type="text_icon_overlap",
        description="German button text directly overlapping absolute-positioned search icon",
        html_snippet='<div id="target" class="icon-btn"><svg class="icon" viewBox="0 0 24 24"><circle cx="11" cy="11" r="8" fill="#6b7280"/></svg><span class="label">Dokumentation</span></div>',
        css_rules=".icon-btn { position: relative; width: 130px; height: 38px; background: #f3f4f6; border-radius: 6px; overflow: hidden; } .icon { position: absolute; left: 10px; top: 10px; width: 18px; height: 18px; } .label { position: absolute; left: 14px; top: 10px; font-size: 14px; color: #111; }",
        target_selector="#target"
    ),
    TestCase(
        id="overlap_fr_cart_badge",
        locale="fr",
        category="text_icon_overlap",
        is_defect_ground_truth=True,
        expected_defect_type="text_icon_overlap",
        description="French long label colliding with cart icon in fixed flex layout",
        html_snippet='<button id="target" class="flex-btn"><span class="txt">Ajouter au panier</span><span class="badge">🛒</span></button>',
        css_rules=".flex-btn { display: flex; width: 115px; height: 38px; align-items: center; justify-content: space-between; overflow: hidden; background: #10b981; color: #fff; padding: 0 4px; font-size: 13px; } .txt { margin-right: -14px; white-space: nowrap; }",
        target_selector="#target"
    ),
    TestCase(
        id="overlap_ar_chevron_btn",
        locale="ar",
        category="text_icon_overlap",
        is_defect_ground_truth=True,
        expected_defect_type="text_icon_overlap",
        description="Arabic button text colliding with chevron due to missing margin in LTR container",
        html_snippet='<div id="target" class="ar-box"><span class="sym">‹</span><span class="lbl">الصفحة الرئيسية</span></div>',
        css_rules=".ar-box { position: relative; width: 110px; height: 36px; background: #e5e7eb; padding: 6px; overflow: hidden; } .sym { position: absolute; right: 8px; font-size: 20px; } .lbl { position: absolute; right: 10px; font-size: 14px; white-space: nowrap; }",
        target_selector="#target"
    ),
    TestCase(
        id="overlap_es_download_btn",
        locale="es",
        category="text_icon_overlap",
        is_defect_ground_truth=True,
        expected_defect_type="text_icon_overlap",
        description="Spanish download button where label covers arrow icon",
        html_snippet='<button id="target" class="btn"><span class="ico">⬇</span><span class="txt">Descargar informe completo</span></button>',
        css_rules=".btn { position: relative; width: 140px; height: 40px; background: #2563eb; color: #fff; overflow: hidden; } .ico { position: absolute; left: 8px; top: 10px; } .txt { position: absolute; left: 12px; top: 11px; font-size: 13px; white-space: nowrap; }",
        target_selector="#target"
    ),
    TestCase(
        id="overlap_ru_refresh_spin",
        locale="ru",
        category="text_icon_overlap",
        is_defect_ground_truth=True,
        expected_defect_type="text_icon_overlap",
        description="Russian refresh button text colliding with spinner glyph",
        html_snippet='<button id="target" class="btn"><span class="spin">↻</span><span class="msg">Обновить данные</span></button>',
        css_rules=".btn { display: flex; width: 120px; height: 36px; align-items: center; background: #374151; color: #fff; overflow: hidden; } .spin { min-width: 20px; margin-right: -10px; } .msg { font-size: 12px; white-space: nowrap; }",
        target_selector="#target"
    ),
    TestCase(
        id="overlap_ja_status_dot",
        locale="ja",
        category="text_icon_overlap",
        is_defect_ground_truth=True,
        expected_defect_type="text_icon_overlap",
        description="Japanese status text sitting directly on top of green status dot",
        html_snippet='<div id="target" class="status-wrap"><span class="dot"></span><span class="txt">稼働中システム</span></div>',
        css_rules=".status-wrap { position: relative; width: 90px; height: 30px; background: #f9fafb; padding: 4px; } .dot { position: absolute; left: 10px; top: 10px; width: 10px; height: 10px; background: #22c55e; border-radius: 50%; } .txt { position: absolute; left: 12px; top: 6px; font-size: 13px; white-space: nowrap; }",
        target_selector="#target"
    ),
    TestCase(
        id="overlap_zh_lock_icon",
        locale="zh",
        category="text_icon_overlap",
        is_defect_ground_truth=True,
        expected_defect_type="text_icon_overlap",
        description="Chinese lock security badge overlapping lock emoji",
        html_snippet='<div id="target" class="lock-btn"><span>🔒</span><span class="t">安全验证中心</span></div>',
        css_rules=".lock-btn { position: relative; width: 85px; height: 34px; background: #fef2f2; color: #991b1b; overflow: hidden; padding: 6px; } .t { position: absolute; left: 10px; font-size: 13px; }",
        target_selector="#target"
    ),
    TestCase(
        id="overlap_ko_dropdown_arrow",
        locale="ko",
        category="text_icon_overlap",
        is_defect_ground_truth=True,
        expected_defect_type="text_icon_overlap",
        description="Korean dropdown select label running into down-caret",
        html_snippet='<div id="target" class="select"><span class="val">데이터베이스 관리</span><span class="arr">▼</span></div>',
        css_rules=".select { position: relative; width: 110px; height: 36px; border: 1px solid #ccc; background: #fff; overflow: hidden; padding: 6px; } .val { font-size: 13px; white-space: nowrap; } .arr { position: absolute; right: 6px; top: 10px; font-size: 10px; background: rgba(255,255,255,0.7); }",
        target_selector="#target"
    ),

    # --- POSITIVE DEFECTS: BIDI / ARABIC INVERSION & DISPLACEMENT (7 cases) ---
    TestCase(
        id="bidi_ar_unisolated_pct",
        locale="ar",
        category="bidi_inversion",
        is_defect_ground_truth=True,
        expected_defect_type="bidi_inversion",
        description="Arabic discount percentage flipped to wrong visual side without isolate",
        html_snippet='<div id="target" class="bidi-box" dir="rtl"><span class="txt">خصم 50% اليوم</span></div>',
        css_rules=".bidi-box { width: 180px; height: 40px; background: #ecfdf5; color: #065f46; font-size: 16px; padding: 8px; }",
        target_selector="#target"
    ),
    TestCase(
        id="bidi_he_ltr_container_mixed",
        locale="he",
        category="bidi_inversion",
        is_defect_ground_truth=True,
        expected_defect_type="bidi_inversion",
        description="Hebrew mixed phone number placed in LTR container causing inverted parenthesis",
        html_snippet='<div id="target" class="he-box"><span>טלפון: (03) 123-4567</span></div>',
        css_rules=".he-box { width: 220px; height: 36px; font-size: 15px; background: #f3f4f6; padding: 6px; direction: ltr; }",
        target_selector="#target"
    ),
    TestCase(
        id="bidi_ar_date_inversion",
        locale="ar",
        category="bidi_inversion",
        is_defect_ground_truth=True,
        expected_defect_type="bidi_inversion",
        description="Arabic release date flipped around slashes in unisolated span",
        html_snippet='<div id="target" class="ar-date" dir="rtl">تاريخ البدء: 2026/11/10!</div>',
        css_rules=".ar-date { width: 220px; height: 36px; font-size: 15px; background: #eff6ff; color: #1e40af; padding: 8px; }",
        target_selector="#target"
    ),
    TestCase(
        id="bidi_ar_english_brand",
        locale="ar",
        category="bidi_inversion",
        is_defect_ground_truth=True,
        expected_defect_type="bidi_inversion",
        description="Arabic sentence wrapping English brand name incorrectly across border",
        html_snippet='<div id="target" class="ar-brand" dir="rtl">مرحبا بكم في Polyglot Engine الآن</div>',
        css_rules=".ar-brand { width: 170px; height: 48px; font-size: 14px; background: #faf5ff; color: #6b21a8; padding: 6px; overflow: hidden; }",
        target_selector="#target"
    ),
    TestCase(
        id="bidi_he_trailing_question",
        locale="he",
        category="bidi_inversion",
        is_defect_ground_truth=True,
        expected_defect_type="bidi_inversion",
        description="Hebrew question mark displaced to opposite side of sentence",
        html_snippet='<div id="target" class="he-q" style="direction: ltr;">האם אתה בטוח?</div>',
        css_rules=".he-q { width: 160px; height: 36px; background: #fef2f2; font-size: 15px; padding: 6px; }",
        target_selector="#target"
    ),
    TestCase(
        id="bidi_ar_price_inverted",
        locale="ar",
        category="bidi_inversion",
        is_defect_ground_truth=True,
        expected_defect_type="bidi_inversion",
        description="Arabic price string with dollar sign flipped onto right side inappropriately",
        html_snippet='<div id="target" class="price" style="direction: ltr;">السعر: $49.99 فقط</div>',
        css_rules=".price { width: 180px; height: 36px; font-size: 15px; background: #f0fdf4; padding: 6px; }",
        target_selector="#target"
    ),
    TestCase(
        id="bidi_fa_version_mixed",
        locale="fa",
        category="bidi_inversion",
        is_defect_ground_truth=True,
        expected_defect_type="bidi_inversion",
        description="Persian text with dot-version number reversed in LTR context",
        html_snippet='<div id="target" class="fa-ver" style="direction: ltr;">نسخه ۲.۴.۰ جدید</div>',
        css_rules=".fa-ver { width: 180px; height: 36px; font-size: 15px; background: #f5f5f4; padding: 6px; }",
        target_selector="#target"
    ),

    # --- NEGATIVE CONTROLS: VALID TIGHT MARGINS & ICONS (7 cases) ---
    TestCase(
        id="clean_de_tight_btn",
        locale="de",
        category="clean_control",
        is_defect_ground_truth=False,
        expected_defect_type=None,
        description="German button with intentionally tight 4px padding but zero collision or clipping",
        html_snippet='<button id="target" class="btn"><span class="ico">🔍</span><span class="txt">Suchen</span></button>',
        css_rules=".btn { display: inline-flex; align-items: center; gap: 4px; padding: 6px 8px; background: #2563eb; color: #fff; font-size: 13px; border: none; border-radius: 4px; } .ico { font-size: 12px; }",
        target_selector="#target"
    ),
    TestCase(
        id="clean_fr_filter_pill",
        locale="fr",
        category="clean_control",
        is_defect_ground_truth=False,
        expected_defect_type=None,
        description="French filter pill with close borders that fully accommodates text",
        html_snippet='<span id="target" class="pill">Actif (12)</span>',
        css_rules=".pill { display: inline-block; padding: 3px 8px; font-size: 12px; background: #dcfce7; color: #166534; border-radius: 9999px; }",
        target_selector="#target"
    ),
    TestCase(
        id="clean_es_cancel_btn",
        locale="es",
        category="clean_control",
        is_defect_ground_truth=False,
        expected_defect_type=None,
        description="Spanish standard cancel button with ample padding",
        html_snippet='<button id="target" class="btn">Cancelar</button>',
        css_rules=".btn { padding: 8px 16px; font-size: 14px; background: #e5e7eb; color: #374151; border: none; border-radius: 6px; }",
        target_selector="#target"
    ),
    TestCase(
        id="clean_it_download_icon",
        locale="it",
        category="clean_control",
        is_defect_ground_truth=False,
        expected_defect_type=None,
        description="Italian download button with clear 8px spacing between icon and text",
        html_snippet='<button id="target" class="btn"><span>📥</span><span>Scarica</span></button>',
        css_rules=".btn { display: inline-flex; align-items: center; gap: 8px; padding: 8px 14px; background: #0284c7; color: #fff; border: none; border-radius: 6px; font-size: 14px; }",
        target_selector="#target"
    ),
    TestCase(
        id="clean_pl_settings_badge",
        locale="pl",
        category="clean_control",
        is_defect_ground_truth=False,
        expected_defect_type=None,
        description="Polish settings label with a badge on the right side cleanly separated",
        html_snippet='<div id="target" class="row"><span>Ustawienia konta</span><span class="badge">NOWE</span></div>',
        css_rules=".row { display: inline-flex; align-items: center; gap: 10px; padding: 6px 12px; background: #f3f4f6; border-radius: 6px; font-size: 13px; } .badge { background: #ef4444; color: #fff; font-size: 10px; padding: 2px 4px; border-radius: 3px; }",
        target_selector="#target"
    ),
    TestCase(
        id="clean_nl_compact_tag",
        locale="nl",
        category="clean_control",
        is_defect_ground_truth=False,
        expected_defect_type=None,
        description="Dutch tag with small font fitting snugly inside container",
        html_snippet='<span id="target" class="tag">Bezig</span>',
        css_rules=".tag { display: inline-block; padding: 2px 6px; font-size: 11px; background: #fef3c7; color: #92400e; border-radius: 4px; }",
        target_selector="#target"
    ),
    TestCase(
        id="clean_sv_icon_button",
        locale="sv",
        category="clean_control",
        is_defect_ground_truth=False,
        expected_defect_type=None,
        description="Swedish save button with icon properly aligned",
        html_snippet='<button id="target" class="btn"><span class="i">💾</span><span class="t">Spara ändringar</span></button>',
        css_rules=".btn { display: inline-flex; align-items: center; gap: 6px; padding: 8px 14px; background: #16a34a; color: #fff; border: none; border-radius: 6px; font-size: 14px; }",
        target_selector="#target"
    ),

    # --- NEGATIVE CONTROLS: VALID BIDI NUMERALS & CURRENCIES (6 cases) ---
    TestCase(
        id="clean_ar_proper_isolate",
        locale="ar",
        category="clean_control",
        is_defect_ground_truth=False,
        expected_defect_type=None,
        description="Arabic text with unicode-bidi isolate correctly positioning 50% discount",
        html_snippet='<div id="target" class="box" dir="rtl">خصم <bdi>50%</bdi> متاح الآن</div>',
        css_rules=".box { width: 200px; padding: 8px 12px; background: #ecfdf5; color: #065f46; font-size: 15px; border-radius: 6px; }",
        target_selector="#target"
    ),
    TestCase(
        id="clean_ar_currency_sar",
        locale="ar",
        category="clean_control",
        is_defect_ground_truth=False,
        expected_defect_type=None,
        description="Arabic price formatted with standard SAR symbol and isolated number",
        html_snippet='<div id="target" class="box" dir="rtl">السعر: <bdi>١٥٠ ر.س</bdi></div>',
        css_rules=".box { width: 180px; padding: 8px 12px; background: #f8fafc; font-size: 15px; border: 1px solid #cbd5e1; border-radius: 6px; }",
        target_selector="#target"
    ),
    TestCase(
        id="clean_he_proper_rtl_num",
        locale="he",
        category="clean_control",
        is_defect_ground_truth=False,
        expected_defect_type=None,
        description="Hebrew text in properly declared RTL container with isolated phone",
        html_snippet='<div id="target" class="box" dir="rtl">טלפון: <bdi>03-1234567</bdi></div>',
        css_rules=".box { width: 200px; padding: 8px 12px; background: #f3f4f6; font-size: 15px; border-radius: 6px; }",
        target_selector="#target"
    ),
    TestCase(
        id="clean_ar_date_isolated",
        locale="ar",
        category="clean_control",
        is_defect_ground_truth=False,
        expected_defect_type=None,
        description="Arabic date wrapped in bdi tag with immaculate visual alignment",
        html_snippet='<div id="target" class="box" dir="rtl">تاريخ: <bdi>2026/11/10</bdi></div>',
        css_rules=".box { width: 190px; padding: 8px 12px; background: #eff6ff; color: #1d4ed8; font-size: 14px; border-radius: 6px; }",
        target_selector="#target"
    ),
    TestCase(
        id="clean_ar_btn_action",
        locale="ar",
        category="clean_control",
        is_defect_ground_truth=False,
        expected_defect_type=None,
        description="Clean Arabic call to action button with native RTL alignment",
        html_snippet='<button id="target" class="btn" dir="rtl">تسجيل الدخول</button>',
        css_rules=".btn { padding: 8px 20px; font-size: 14px; background: #2563eb; color: #fff; border: none; border-radius: 6px; }",
        target_selector="#target"
    ),
    TestCase(
        id="clean_he_simple_btn",
        locale="he",
        category="clean_control",
        is_defect_ground_truth=False,
        expected_defect_type=None,
        description="Clean Hebrew submission button with proper spacing",
        html_snippet='<button id="target" class="btn" dir="rtl">שמור שינויים</button>',
        css_rules=".btn { padding: 8px 20px; font-size: 14px; background: #16a34a; color: #fff; border: none; border-radius: 6px; }",
        target_selector="#target"
    ),

    # --- NEGATIVE CONTROLS: COMPLEX SCRIPTS & INTENTIONAL WRAPPING (12 cases) ---
    TestCase(
        id="clean_ja_font_rendering",
        locale="ja",
        category="clean_control",
        is_defect_ground_truth=False,
        expected_defect_type=None,
        description="Japanese kanji and hiragana rendered cleanly with appropriate line height",
        html_snippet='<button id="target" class="btn">アカウント設定の変更</button>',
        css_rules=".btn { padding: 8px 16px; font-size: 14px; line-height: 1.5; background: #334155; color: #fff; border: none; border-radius: 6px; }",
        target_selector="#target"
    ),
    TestCase(
        id="clean_hi_matra_rendering",
        locale="hi",
        category="clean_control",
        is_defect_ground_truth=False,
        expected_defect_type=None,
        description="Hindi Devanagari text with conjuncts and matras fitting container height",
        html_snippet='<button id="target" class="btn">खाता सेटिंग बदलें</button>',
        css_rules=".btn { padding: 8px 16px; font-size: 15px; line-height: 1.6; background: #ea580c; color: #fff; border: none; border-radius: 6px; }",
        target_selector="#target"
    ),
    TestCase(
        id="clean_zh_pill_badge",
        locale="zh",
        category="clean_control",
        is_defect_ground_truth=False,
        expected_defect_type=None,
        description="Chinese simplified characters in small badge without cutoff",
        html_snippet='<span id="target" class="badge">已完成</span>',
        css_rules=".badge { display: inline-block; padding: 3px 8px; font-size: 12px; background: #dcfce7; color: #15803d; border-radius: 4px; }",
        target_selector="#target"
    ),
    TestCase(
        id="clean_ko_action_btn",
        locale="ko",
        category="clean_control",
        is_defect_ground_truth=False,
        expected_defect_type=None,
        description="Korean Hangul action button with adequate horizontal margin",
        html_snippet='<button id="target" class="btn">새 프로젝트 생성</button>',
        css_rules=".btn { padding: 9px 18px; font-size: 14px; background: #6366f1; color: #fff; border: none; border-radius: 6px; }",
        target_selector="#target"
    ),
    TestCase(
        id="clean_en_twoline_wrap",
        locale="en",
        category="clean_control",
        is_defect_ground_truth=False,
        expected_defect_type=None,
        description="English banner text intentionally wrapped cleanly across two lines",
        html_snippet='<div id="target" class="wrap-box">Download our complete annual security report</div>',
        css_rules=".wrap-box { width: 180px; padding: 10px; font-size: 13px; line-height: 1.4; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; }",
        target_selector="#target"
    ),
    TestCase(
        id="clean_de_twoline_wrap",
        locale="de",
        category="clean_control",
        is_defect_ground_truth=False,
        expected_defect_type=None,
        description="German phrase wrapped logically across two balanced lines with ample container height",
        html_snippet='<div id="target" class="wrap-box">Hier finden Sie alle aktuellen Systemberichte</div>',
        css_rules=".wrap-box { width: 190px; min-height: 50px; padding: 8px 12px; font-size: 13px; line-height: 1.4; background: #eff6ff; color: #1e3a8a; border-radius: 6px; }",
        target_selector="#target"
    ),
    TestCase(
        id="clean_fr_twoline_btn",
        locale="fr",
        category="clean_control",
        is_defect_ground_truth=False,
        expected_defect_type=None,
        description="French multi-line button with centered text and comfortable vertical padding",
        html_snippet='<button id="target" class="btn"><span>Accepter les conditions<br>d\'utilisation</span></button>',
        css_rules=".btn { width: 170px; padding: 8px 12px; font-size: 12px; line-height: 1.3; text-align: center; background: #2563eb; color: #fff; border: none; border-radius: 6px; }",
        target_selector="#target"
    ),
    TestCase(
        id="clean_th_thai_vowels",
        locale="th",
        category="clean_control",
        is_defect_ground_truth=False,
        expected_defect_type=None,
        description="Thai text with upper tone marks and lower vowels completely intact",
        html_snippet='<button id="target" class="btn">บันทึกข้อมูลผู้ใช้</button>',
        css_rules=".btn { padding: 8px 18px; font-size: 15px; line-height: 1.7; background: #0d9488; color: #fff; border: none; border-radius: 6px; }",
        target_selector="#target"
    ),
    TestCase(
        id="clean_es_floating_badge",
        locale="es",
        category="clean_control",
        is_defect_ground_truth=False,
        expected_defect_type=None,
        description="Spanish card with notification counter badge floating correctly at top right corner",
        html_snippet='<div id="target" class="card-wrap"><button class="btn">Mensajes</button><span class="badge">3</span></div>',
        css_rules=".card-wrap { position: relative; display: inline-block; } .btn { padding: 8px 16px; font-size: 14px; background: #f3f4f6; border: 1px solid #d1d5db; border-radius: 6px; } .badge { position: absolute; top: -6px; right: -6px; width: 18px; height: 18px; line-height: 18px; text-align: center; background: #ef4444; color: #fff; font-size: 11px; border-radius: 50%; }",
        target_selector="#target"
    ),
    TestCase(
        id="clean_hi_card_headline",
        locale="hi",
        category="clean_control",
        is_defect_ground_truth=False,
        expected_defect_type=None,
        description="Hindi headline text with standard Devanagari font stack and ample padding",
        html_snippet='<div id="target" class="box">सुरक्षित ऑनलाइन भुगतान</div>',
        css_rules=".box { display: inline-block; padding: 8px 16px; font-size: 15px; background: #fef08a; color: #713f12; border-radius: 6px; }",
        target_selector="#target"
    ),
    TestCase(
        id="clean_ja_toggle_switch",
        locale="ja",
        category="clean_control",
        is_defect_ground_truth=False,
        expected_defect_type=None,
        description="Japanese toggle switch with on/off label properly offset",
        html_snippet='<div id="target" class="toggle"><span class="lbl">通知</span><span class="switch"><span class="knob"></span></span></div>',
        css_rules=".toggle { display: inline-flex; align-items: center; gap: 8px; font-size: 13px; } .switch { width: 34px; height: 18px; background: #3b82f6; border-radius: 9999px; position: relative; } .knob { position: absolute; right: 2px; top: 2px; width: 14px; height: 14px; background: #fff; border-radius: 50%; }",
        target_selector="#target"
    ),
    TestCase(
        id="clean_de_card_headline",
        locale="de",
        category="clean_control",
        is_defect_ground_truth=False,
        expected_defect_type=None,
        description="German compound heading that fits cleanly within card width",
        html_snippet='<h3 id="target" class="head">Sicherheitsüberprüfung</h3>',
        css_rules=".head { margin: 0; padding: 6px 10px; font-size: 15px; font-weight: 600; color: #0f172a; background: #f1f5f9; border-radius: 4px; display: inline-block; }",
        target_selector="#target"
    ),
]


@dataclass
class ModelPrediction:
    defect: bool
    defect_type: Optional[str]
    confidence: float
    reason: str
    latency_ms: float
    raw_response: str


def render_and_capture_cases(
    cases: List[TestCase],
    output_dir: Path
) -> Dict[str, Path]:
    """Uses Playwright to render all 50 test cases and capture cropped PNGs."""
    from playwright.sync_api import sync_playwright

    output_dir.mkdir(parents=True, exist_ok=True)
    images_dir = output_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    print(f"[*] Rendering {len(cases)} test cases using Playwright...")
    image_paths: Dict[str, Path] = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()

        for case in cases:
            html = f"""
            <!DOCTYPE html>
            <html lang="{case.locale}">
            <head>
                <meta charset="UTF-8">
                <style>
                    body {{
                        margin: 0;
                        padding: 24px;
                        background: #ffffff;
                        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                    }}
                    {case.css_rules}
                </style>
            </head>
            <body>
                {case.html_snippet}
            </body>
            </html>
            """
            page.set_content(html, wait_until="networkidle")
            target = page.locator(case.target_selector)
            img_path = images_dir / f"{case.id}.png"
            target.screenshot(path=str(img_path))
            image_paths[case.id] = img_path

        browser.close()

    print(f"[+] All {len(cases)} screenshots rendered to {images_dir}")
    return image_paths


PROMPT_TEMPLATE = """You are an expert visual UI defect inspector.
Analyze this cropped image of a UI component (button, badge, card, or label).
Determine if there is any visual defect, such as:
1. "text_clipped": Text cut off by borders, truncated prematurely, or clipped ascenders/descenders.
2. "text_icon_overlap": Text colliding with or overlapping an icon, badge, or chevron.
3. "bidi_inversion": Arabic/Hebrew text where numbers, percentages, currency, or punctuation are placed on the wrong visual side due to bidirectional layout errors.
4. "awkward_wrap": Text awkwardly wrapped or broken.

NOTE: Tight margins that do NOT clip text, intentional clean multiline wrapping, and correct RTL numbers/currency are NOT defects.

Return strictly a JSON object:
{
  "defect": true/false,
  "defect_type": "text_clipped" | "text_icon_overlap" | "bidi_inversion" | "awkward_wrap" | null,
  "confidence": 0.0 to 1.0,
  "reason": "Brief explanation of the visual judgment"
}
"""


class MoondreamClient:
    """Pluggable adapter for Moondream 2 inference."""

    def __init__(self, backend: str = "mock", endpoint: Optional[str] = None):
        self.backend = backend
        self.endpoint = endpoint
        self._init_backend()

    def _init_backend(self):
        if self.backend == "ollama":
            import urllib.request
            self.api_url = self.endpoint or "http://localhost:11434/api/generate"
        elif self.backend == "openai_compat":
            import openai
            self.client = openai.OpenAI(base_url=self.endpoint or "http://localhost:8000/v1", api_key=os.getenv("OPENAI_API_KEY", "EMPTY"))
        elif self.backend == "mock":
            pass
        else:
            raise ValueError(f"Unsupported backend: {self.backend}. Choose 'mock', 'ollama', or 'openai_compat'")

    def predict(self, image_path: Path) -> ModelPrediction:
        start_time = time.perf_counter()

        with open(image_path, "rb") as f:
            img_bytes = f.read()
            b64_img = base64.b64encode(img_bytes).decode("utf-8")

        if self.backend == "mock":
            # Deterministic mock simulating an imperfect vision model for testing benchmark mechanics
            stem = image_path.stem
            is_defect = not stem.startswith("clean_")
            defect_type = "text_clipped" if "clip" in stem else ("text_icon_overlap" if "overlap" in stem else ("bidi_inversion" if "bidi" in stem else None))
            # Inject a realistic 5% mock imperfection
            if stem == "clean_de_tight_btn":
                is_defect = True  # Simulated false positive on tight margin
                defect_type = "text_clipped"
            latency = (time.perf_counter() - start_time) * 1000 + 42.0
            return ModelPrediction(
                defect=is_defect,
                defect_type=defect_type,
                confidence=0.92 if is_defect else 0.88,
                reason="Simulated prediction for benchmark evaluation",
                latency_ms=round(latency, 2),
                raw_response=json.dumps({"defect": is_defect, "defect_type": defect_type, "confidence": 0.90})
            )

        elif self.backend == "ollama":
            import urllib.request
            payload = {
                "model": "moondream",
                "prompt": PROMPT_TEMPLATE,
                "images": [b64_img],
                "stream": False,
                "format": "json"
            }
            req = urllib.request.Request(
                self.api_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                raw_resp = data.get("response", "{}")
                parsed = json.loads(raw_resp)
                latency = (time.perf_counter() - start_time) * 1000
                return ModelPrediction(
                    defect=bool(parsed.get("defect", False)),
                    defect_type=parsed.get("defect_type"),
                    confidence=float(parsed.get("confidence", 0.5)),
                    reason=str(parsed.get("reason", "")),
                    latency_ms=round(latency, 2),
                    raw_response=raw_resp
                )

        elif self.backend == "openai_compat":
            response = self.client.chat.completions.create(
                model="moondream2",
                messages=[
                    {"role": "user", "content": [
                        {"type": "text", "text": PROMPT_TEMPLATE},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_img}"}}
                    ]}
                ],
                response_format={"type": "json_object"}
            )
            raw_resp = response.choices[0].message.content or "{}"
            parsed = json.loads(raw_resp)
            latency = (time.perf_counter() - start_time) * 1000
            return ModelPrediction(
                defect=bool(parsed.get("defect", False)),
                defect_type=parsed.get("defect_type"),
                confidence=float(parsed.get("confidence", 0.5)),
                reason=str(parsed.get("reason", "")),
                latency_ms=round(latency, 2),
                raw_response=raw_resp
            )

        raise RuntimeError("Unknown backend")


def run_benchmark(
    backend: str = "mock",
    endpoint: Optional[str] = None,
    output_dir: Path = Path("reports/moondream_benchmark")
) -> Dict[str, Any]:
    """Executes the full 50-case benchmark, evaluates accuracy, and outputs metrics."""
    output_dir.mkdir(parents=True, exist_ok=True)
    images = render_and_capture_cases(BENCHMARK_CASES, output_dir)

    client = MoondreamClient(backend=backend, endpoint=endpoint)
    print(f"[*] Running Moondream benchmark using backend: {backend}...")

    results: List[Dict[str, Any]] = []
    tp = fp = tn = fn = 0
    latencies: List[float] = []

    for case in BENCHMARK_CASES:
        img_path = images[case.id]
        pred = client.predict(img_path)
        latencies.append(pred.latency_ms)

        is_tp = case.is_defect_ground_truth and pred.defect
        is_tn = (not case.is_defect_ground_truth) and (not pred.defect)
        is_fp = (not case.is_defect_ground_truth) and pred.defect
        is_fn = case.is_defect_ground_truth and (not pred.defect)

        if is_tp: tp += 1
        elif is_tn: tn += 1
        elif is_fp: fp += 1
        elif is_fn: fn += 1

        results.append({
            "id": case.id,
            "locale": case.locale,
            "category": case.category,
            "ground_truth_defect": case.is_defect_ground_truth,
            "predicted_defect": pred.defect,
            "expected_type": case.expected_defect_type,
            "predicted_type": pred.defect_type,
            "confidence": pred.confidence,
            "reason": pred.reason,
            "latency_ms": pred.latency_ms,
            "verdict": "TP" if is_tp else ("TN" if is_tn else ("FP" if is_fp else "FN"))
        })

    total = len(BENCHMARK_CASES)
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    mean_latency = sum(latencies) / len(latencies) if latencies else 0.0

    summary = {
        "total_cases": total,
        "true_positives": tp,
        "true_negatives": tn,
        "false_positives": fp,
        "false_negatives": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1_score": round(f1, 4),
        "false_positive_rate": round(fpr, 4),
        "mean_latency_ms": round(mean_latency, 2),
        "backend": backend,
        "results": results
    }

    report_path = output_dir / "benchmark_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 60)
    print(" MOONDREAM 2 BENCHMARK RESULTS")
    print("=" * 60)
    print(f"Total Test Cases:        {total} (25 defects, 25 clean controls)")
    print(f"Precision:               {precision * 100:.2f}%")
    print(f"Recall:                  {recall * 100:.2f}%")
    print(f"F1 Score:                {f1:.4f}")
    print(f"False Positive Rate:     {fpr * 100:.2f}% ({fp}/25 clean controls falsely flagged)")
    print(f"Mean Latency:            {mean_latency:.2f} ms")
    print(f"Detailed Report Saved:   {report_path}")
    print("=" * 60)

    return summary


def main():
    parser = argparse.ArgumentParser(description="Benchmark Moondream 2 for Multilingual UI Defect Inspection")
    parser.add_argument("--backend", choices=["mock", "ollama", "openai_compat"], default="mock",
                        help="Inference backend: 'mock' for local offline test, 'ollama' or 'openai_compat' for live model")
    parser.add_argument("--endpoint", default=None, help="Endpoint URL for ollama or OpenAI-compatible server")
    parser.add_argument("--output-dir", default="reports/moondream_benchmark", help="Directory for images and report")
    args = parser.parse_args()

    run_benchmark(backend=args.backend, endpoint=args.endpoint, output_dir=Path(args.output_dir))


if __name__ == "__main__":
    main()
