# Polyglot Engine — Autonomous Multilingual Layout Scanner & Verified Source Repair CLI

> **Polyglot Engine is a developer-first CLI that scans, diagnoses and repairs multilingual UI problems directly inside your codebase.**
>
> *Polyglot aims to make multilingual UI testing actionable by connecting browser-level layout defects to their linguistic or CSS causes, then generating and verifying targeted source-code repairs.*

---

## 🏗️ 6-Layer Product Architecture

Polyglot Engine connects browser inspection, localization context, root-cause diagnosis, and source-code repair across six distinct architectural layers:

```text
┌────────────────────────────────────────────────────────────────────────┐
│ 1. Polyglot Browser Scanner                                            │
│    Playwright + whole-DOM tree walker + CSS computed styles + ranges   │
├────────────────────────────────────────────────────────────────────────┤
│ 2. Visual Verification                                                 │
│    Screenshot capture + sub-pixel physical reflow & collision bounds   │
├────────────────────────────────────────────────────────────────────────┤
│ 3. Root-Cause Engine                                                   │
│    Classifies: linguistic verbosity, rigid CSS, flex-wrap, BiDi        │
├────────────────────────────────────────────────────────────────────────┤
│ 4. Translation Repair                                                  │
│    Closed-loop candidate backtracking: standard -> compact -> short    │
├────────────────────────────────────────────────────────────────────────┤
│ 5. CSS Repair                                                          │
│    Targeted source patches on responsible stylesheets (CSS-aware)      │
├────────────────────────────────────────────────────────────────────────┤
│ 6. Cross-Locale Regression Verification                                │
│    Rebuild, reload, rescan across locales & viewports; report rate     │
└────────────────────────────────────────────────────────────────────────┘
```

---

## ⚡ The Core Problem & Differentiated Proposition

Existing localization tools (Phrase, Lokalise) manage strings in databases, while visual QA platforms (Applitools, Percy) capture screenshot baselines in cloud dashboards.

Polyglot focuses on a terminal-first, visual-rich engineering workflow directly inside the codebase:
1. **Identify whether the translation or the CSS constraint caused the problem.**
2. **Determine if an approved compact translation solves it without changing code.**
3. **If not, calculate the exact minimal CSS declaration on the responsible stylesheet.**
4. **Apply the patch to source code and verify that a clean browser reload clears defects.**
5. **Run cross-locale regression verification across other languages and responsive breakpoints to guarantee no new breakages were introduced.**

---

## 🚀 Developer CLI Workflow

Polyglot provides a complete command-line workflow controlled directly from your terminal, backed by local interactive HTML reports and verified Git diffs:

```bash
# 1. Initialize project configuration (creates polyglot.config.json)
polyglot init --url http://localhost:3000 --locales de-DE,ar-SA,ja-JP --viewports desktop,mobile

# 2. Whole-DOM multilingual audit across locales & viewports (exits with code 1 on defects)
polyglot scan http://localhost:3000 --locales de-DE,ar-SA --viewports desktop,mobile --fail-on any

# 3. Open the standalone interactive HTML visual report in your default browser
polyglot report

# 4. Inspect root causes and layout constraints from JSON report
polyglot diagnose polyglot_audit_report.json

# 5. Execute closed-loop multi-candidate repair & generate verified Git diff patch
polyglot fix http://localhost:3000 --locales de-DE,ar-SA --repo-path . --verify

# 6. Verify cross-locale & multi-viewport regression immunity (Layer 6)
polyglot verify http://localhost:3000 --locales en-US,de-DE,ar-SA --viewports desktop,mobile
```

---

## 🤖 Turnkey GitHub Action Integration

Drop Polyglot directly into `.github/workflows/polyglot.yml` to audit pull requests automatically, fail builds on layout breakage, write a formatted Markdown scorecard to `$GITHUB_STEP_SUMMARY`, and upload the interactive visual HTML report as a build artifact:

```yaml
- name: Run Polyglot Localization & Layout Audit
  uses: Raghavender1234/polyglot-engine@main
  with:
    url: 'http://localhost:3000'
    locales: 'de-DE,ar-SA,ja-JP'
    viewports: 'desktop,mobile'
    fail-on: 'any'
```

---

## 🔬 Standalone Vision Model Benchmark (`scripts/benchmark_moondream.py`)

To evaluate optional visual AI verification (Moondream 3.1 / 2) against deterministic Playwright geometry without bloating core CLI runs, use the standalone 50-case multilingual benchmark harness:

```bash
# Offline test & 50-case Playwright crop generator
python scripts/benchmark_moondream.py --backend mock

# Live evaluation against Moondream 3.1 Cloud API
python scripts/benchmark_moondream.py --backend moondream3_api --api-key $MOONDREAM_API_KEY
```

---

## 📁 Repository Structure

```text
polyglot-engine/
├── polyglot/                   # Modular Autonomous Layout & Closed-Loop Repair Package
│   ├── __init__.py             # Version 1.3.0
│   ├── cli.py                  # Developer CLI (init, scan, report, fix/repair, verify, diagnose)
│   ├── scanner.py              # Whole-DOM element discovery & tree-walker text extractor
│   ├── detector.py             # Whole-page collision, overflow & range-based BiDi detector
│   ├── diagnosis.py            # Computed layout constraint & root-cause analyzer
│   ├── patcher.py              # Dynamic geometry CSS generator & Git diff patcher
│   ├── repair.py               # Closed-loop backtracking repair & cross-locale verifier
│   └── reporting.py            # Interactive HTML/JSON reporting with filter tabs & copyable diffs
├── app/                        # Supporting Headless Shaping API Microservice
│   ├── main.py                 # FastAPI routes, rate limiter, and core pipeline
│   ├── models.py               # Pydantic schemas (Request/Response/Metrics)
│   ├── database.py             # SQLite manager: orgs, hashed keys, cache
│   └── engines/
│       ├── harfbuzz_meter.py   # HarfBuzz OpenType C-shaping engine (<1.5ms)
│       ├── bidi_shield.py      # Unicode isolate injection (\u2066..\u2069)
│       ├── css_mapper.py       # Script-specific CSS properties & line heights
│       └── llm_translator.py   # 1-pass multi-variant translation (gpt-4o-mini + fallback)
├── scripts/
│   ├── benchmark_moondream.py  # Standalone 50-case Moondream 3.1 visual QA benchmark
│   └── ci_check.py             # Headless JSON locale file verifier
├── tests/
│   ├── test_cli.py             # CLI commands, scorecards, config init & exit code tests
│   ├── test_polyglot_modules.py# Patcher, detector, diagnosis, BiDi & reporting tests
│   ├── test_api.py             # API endpoint integration tests
│   ├── test_bidi_shield.py     # BiDi isolation tests
│   ├── test_harfbuzz.py        # HarfBuzz pixel measurement & scaling tests
│   └── test_razorpay.py        # Security & key issuance tests
├── action.yml                  # Composite GitHub Action definition
├── pyproject.toml              # Build config & `polyglot` console script entrypoint
└── requirements.txt
```

---

## ⚡ Quickstart

### 1. Install & Run the Test Suite
```bash
pip install -e .
playwright install chromium
pytest -v
```

### 2. Audit & Repair a Local Web Application
```bash
# Start sample server & interactive playground
uvicorn app.main:app --reload --port 8000

# Scan in another terminal
polyglot scan http://localhost:8000/static/showcase.html --locales de-DE,ar-SA

# View interactive visual report
polyglot report

# Run closed-loop repair and generate verified Git diff
polyglot fix http://localhost:8000/static/showcase.html --locales de-DE --repo-path .
```
