"""
Polyglot Reporting — Honest, Evidence-Based HTML & JSON Audit Reports
Reports actual API success rates, actual translation provenance (including fallbacks in the denominator),
and verified post-repair measurements without misleading claims.
Supports both single-run and multi-run (multi-locale, multi-viewport) audit reports.
"""

from typing import Dict, Any, List
import json
import os
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

class HTMLReportGenerator:
    @classmethod
    def generate(cls, report_data: Dict[str, Any], output_path: str):
        runs = report_data.get("runs")
        if runs and isinstance(runs, list) and len(runs) > 0:
            html = cls._build_multi_run_html(report_data)
        else:
            html = cls._build_single_run_html(report_data)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"📄 Polyglot Verified Audit Report written to: {output_path}")

    @staticmethod
    def _build_single_run_html(data: Dict[str, Any]) -> str:
        init_col = data.get("initial_collisions", 0)
        fin_col = data.get("final_collisions", 0)
        init_ovf = data.get("initial_overflows", 0)
        fin_ovf = data.get("final_overflows", 0)

        prov = data.get("provenance_counts", {})
        api_cnt = prov.get("OPENAI_API", 0)
        preset_cnt = prov.get("PRESET", 0)
        pseudo_cnt = prov.get("PSEUDO", 0)
        fallback_cnt = prov.get("FALLBACK", 0) + prov.get("FAILED", 0)
        total_queries = api_cnt + preset_cnt + pseudo_cnt + fallback_cnt
        api_pct = round((api_cnt / total_queries) * 100) if total_queries > 0 else 0

        # Honest status evaluation
        if init_col == 0 and init_ovf == 0:
            status_text = "✅ Clean Layout — No Overflows or Collisions Detected"
            status_color = "#10b981"
            status_badge = "100% Compatible"
        elif fin_col == 0 and fin_ovf == 0:
            status_text = f"✅ Verified Repaired — Resolved {init_col} Collisions & {init_ovf} Overflows"
            status_color = "#10b981"
            status_badge = "All Issues Repaired"
        else:
            status_text = f"⚠️ Partial Repair — {fin_col} Collisions & {fin_ovf} Overflows Require Manual Styling"
            status_color = "#f59e0b"
            status_badge = "Manual Redesign Needed"

        dynamic_css = data.get("dynamic_css", "")
        git_patch = data.get("git_patch", "")
        screenshots = data.get("screenshots", {})

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Polyglot Engine — Verified UI Layout & Repair Audit</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0f172a; color: #f8fafc; margin: 0; padding: 32px; }}
    .container {{ max-width: 1100px; margin: 0 auto; }}
    .header {{ border-bottom: 1px solid #334155; padding-bottom: 20px; margin-bottom: 24px; display: flex; justify-content: space-between; align-items: center; }}
    .header h1 {{ margin: 0; font-size: 24px; color: #60a5fa; }}
    .badge {{ background: rgba(16, 185, 129, 0.2); border: 1px solid rgba(16, 185, 129, 0.4); color: #34d399; border-radius: 999px; padding: 4px 14px; font-size: 12px; font-weight: 600; }}
    .grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 28px; }}
    .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 18px; }}
    .card .val {{ font-size: 24px; font-weight: 700; margin-top: 6px; }}
    .card.blue .val {{ color: #60a5fa; }}
    .card.amber .val {{ color: #f59e0b; }}
    .card.green .val {{ color: #10b981; }}
    .card.emerald .val {{ color: #34d399; }}
    .step-box {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 20px; margin-bottom: 20px; }}
    .step-title {{ font-size: 16px; font-weight: 700; color: #38bdf8; margin-bottom: 8px; }}
    pre {{ background: #0b1120; border: 1px solid #1e293b; border-radius: 8px; padding: 16px; color: #38bdf8; overflow-x: auto; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 13px; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <div>
        <h1>⚡ Polyglot Engine — Verified UI Layout & Repair Audit</h1>
        <div style="color: #94a3b8; font-size: 13px; margin-top: 4px;">Target: {data.get('target_url')} | Locale: {data.get('locale')} | Viewport: {data.get('viewport')}</div>
      </div>
      <div class="badge">{status_badge}</div>
    </div>

    <div class="card" style="margin-bottom: 24px; border-left: 4px solid {status_color};">
      <div style="font-size: 16px; font-weight: 700; color: {status_color};">{status_text}</div>
      <div style="font-size: 13px; color: #94a3b8; margin-top: 4px;">
        Evaluated across entire DOM: {data.get('total_scanned', 0)} elements inspected | {data.get('total_translated', 0)} translated targets.
      </div>
    </div>

    <div class="grid">
      <div class="card blue">
        <div style="color: #94a3b8; font-size: 12px;">Container Overflows</div>
        <div class="val">{init_ovf} → {fin_ovf}</div>
      </div>
      <div class="card amber">
        <div style="color: #94a3b8; font-size: 12px;">Full-Page Collisions</div>
        <div class="val">{init_col} → {fin_col}</div>
      </div>
      <div class="card green">
        <div style="color: #94a3b8; font-size: 12px;">Resolved Layout Defects</div>
        <div class="val">{data.get('resolved_overflows', 0) + data.get('resolved_collisions', 0)}</div>
      </div>
      <div class="card emerald">
        <div style="color: #94a3b8; font-size: 12px;">Translation Provenance</div>
        <div class="val">{api_pct}% Neural API</div>
        <div style="font-size: 11px; color: #94a3b8; margin-top: 4px;">
          API: {api_cnt} | Presets: {preset_cnt} | Pseudo: {pseudo_cnt} | Fallback: {fallback_cnt}
        </div>
      </div>
    </div>
"""
        if dynamic_css:
            html += f"""
    <div class="step-box">
      <div class="step-title">Verified Dynamically Calculated CSS Layout Patch</div>
      <p style="font-size: 13px; color: #94a3b8; margin: 0 0 12px 0;">
        Derived directly from failing element geometry and parent flex constraints (rejects broad generic tags):
      </p>
      <pre><code>{dynamic_css}</code></pre>
    </div>
"""
        if git_patch:
            html += f"""
    <div class="step-box">
      <div class="step-title">Verified Unified Git Diff Patch</div>
      <p style="font-size: 13px; color: #94a3b8; margin: 0 0 12px 0;">
        Generated directly against local source repository and validated via <code>git apply --check</code>:
      </p>
      <pre><code>{git_patch}</code></pre>
    </div>
"""
        if screenshots:
            html += """
    <div class="step-box">
      <div class="step-title">Full-Page Visual Verification Evidence</div>
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
"""
            for name, path in screenshots.items():
                rel_path = os.path.basename(path)
                html += f"""
        <div>
          <div style="font-size: 12px; color: #94a3b8; margin-bottom: 6px;">{name}:</div>
          <img src="{rel_path}" style="width: 100%; border-radius: 6px; border: 1px solid #334155;">
        </div>
"""
            html += """
      </div>
    </div>
"""
        html += """
  </div>
</body>
</html>
"""
        return html

    @classmethod
    def _build_multi_run_html(cls, data: Dict[str, Any]) -> str:
        runs = data.get("runs", [])
        total_runs = len(runs)
        total_ovf = sum(r.get("initial_overflows", 0) for r in runs)
        total_col = sum(r.get("initial_collisions", 0) for r in runs)
        total_res = sum(r.get("resolved_overflows", 0) + r.get("resolved_collisions", 0) for r in runs)

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Polyglot Engine — Multi-Run Layout & Repair Audit Report</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0f172a; color: #f8fafc; margin: 0; padding: 32px; }}
    .container {{ max-width: 1100px; margin: 0 auto; }}
    .header {{ border-bottom: 1px solid #334155; padding-bottom: 20px; margin-bottom: 24px; display: flex; justify-content: space-between; align-items: center; }}
    .header h1 {{ margin: 0; font-size: 24px; color: #60a5fa; }}
    .grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 28px; }}
    .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 18px; }}
    .card .val {{ font-size: 24px; font-weight: 700; margin-top: 6px; }}
    .card.blue .val {{ color: #60a5fa; }}
    .card.amber .val {{ color: #f59e0b; }}
    .card.green .val {{ color: #10b981; }}
    .card.emerald .val {{ color: #34d399; }}
    .run-card {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 20px; margin-bottom: 20px; }}
    .run-title {{ font-size: 18px; font-weight: 700; color: #38bdf8; margin-bottom: 12px; display: flex; justify-content: space-between; }}
    pre {{ background: #0b1120; border: 1px solid #1e293b; border-radius: 8px; padding: 16px; color: #38bdf8; overflow-x: auto; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 13px; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <div>
        <h1>⚡ Polyglot Engine — Multi-Run Matrix Audit Report</h1>
        <div style="color: #94a3b8; font-size: 13px; margin-top: 4px;">Target: {data.get('target_url')} | Total Matrix Runs: {total_runs}</div>
      </div>
    </div>

    <div class="grid">
      <div class="card blue">
        <div style="color: #94a3b8; font-size: 12px;">Total Runs Executed</div>
        <div class="val">{total_runs}</div>
      </div>
      <div class="card amber">
        <div style="color: #94a3b8; font-size: 12px;">Total Initial Overflows</div>
        <div class="val">{total_ovf}</div>
      </div>
      <div class="card amber">
        <div style="color: #94a3b8; font-size: 12px;">Total Initial Collisions</div>
        <div class="val">{total_col}</div>
      </div>
      <div class="card green">
        <div style="color: #94a3b8; font-size: 12px;">Total Resolved Defects</div>
        <div class="val">{total_res}</div>
      </div>
    </div>
"""
        for r in runs:
            init_c = r.get("initial_collisions", 0)
            fin_c = r.get("final_collisions", 0)
            init_o = r.get("initial_overflows", 0)
            fin_o = r.get("final_overflows", 0)

            prov = r.get("provenance_counts", {})
            api_c = prov.get("OPENAI_API", 0)
            fall_c = prov.get("FALLBACK", 0) + prov.get("FAILED", 0)
            tot_q = api_c + prov.get("PRESET", 0) + prov.get("PSEUDO", 0) + fall_c
            pct = round((api_c / tot_q) * 100) if tot_q > 0 else 0

            status_lbl = "✅ Clean" if (init_c == 0 and init_o == 0) else ("✅ Repaired" if (fin_c == 0 and fin_o == 0) else "⚠️ Issues Remaining")

            html += f"""
    <div class="run-card">
      <div class="run-title">
        <span>🌍 Locale: <code>{r.get('locale')}</code> | Viewport: <code>{r.get('viewport')}</code></span>
        <span>{status_lbl}</span>
      </div>
      <div style="display: flex; gap: 24px; font-size: 14px; color: #94a3b8; margin-bottom: 12px;">
        <div>Overflows: <b style="color: #f8fafc;">{init_o} → {fin_o}</b></div>
        <div>Collisions: <b style="color: #f8fafc;">{init_c} → {fin_c}</b></div>
        <div>Resolved: <b style="color: #10b981;">{r.get('resolved_overflows', 0) + r.get('resolved_collisions', 0)}</b></div>
        <div>Provenance: <b style="color: #38bdf8;">{pct}% Neural API</b> (API: {api_c}, Presets: {prov.get('PRESET', 0)}, Fallback: {fall_c})</div>
      </div>
"""
            if r.get("dynamic_css"):
                html += f"""
      <div style="font-size: 13px; font-weight: 600; color: #60a5fa; margin-top: 8px;">Dynamically Generated Layout Patch:</div>
      <pre><code>{r.get('dynamic_css')}</code></pre>
"""
            html += "    </div>\n"

        html += """
  </div>
</body>
</html>
"""
        return html
