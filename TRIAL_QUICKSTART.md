# Polyglot Engine: Developer Trial Quick-Start Cheatsheet
(Give this 1-page cheatsheet to each trial participant)

Welcome to the **Polyglot Engine** developer trial!

Polyglot is an automated, developer-first tool that detects, diagnoses, and repairs multilingual layout regressions (like German text expansion, Arabic/Hebrew BiDi flaws, and mobile viewport clipping) directly inside your codebase.

---

## 🚀 Quick-Start Instructions

You can run Polyglot directly using `npx`:

### 1. Initialize Configuration
In your project repository (or any test directory):
```bash
npx polyglot init
```
This generates a `polyglot.config.json` where you can set your target URL (e.g. `http://localhost:3000` or staging), locales, and viewports.

---

### 2. Run a Multilingual Audit Scan
Audit your application across languages and viewports:
```bash
npx polyglot scan
```
You will see an immediate terminal ASCII scorecard summarizing container overflows, collisions, and BiDi defects.

---

### 3. Inspect the Visual Evidence & Diffs
Open the interactive HTML audit report:
```bash
npx polyglot report
```
Inspect before/after screenshots, filter defects by category, and review root-cause explanations.

---

### 4. Propose Safe Source-Code Repairs
Generate a unified Git diff (`.patch`) for your stylesheets:
```bash
npx polyglot fix --repo-path .
```
*Note: Your git working tree remains clean by default. The repair runs a browser verification and saves the verified patch file for your review.*

---

### 5. Verify Cross-Locale Regressions
Ensure fixes in one locale don't damage others:
```bash
npx polyglot verify
```

---

## 📝 Trial Feedback
When you finish exploring, please let us know:
1. Did installation and scanning work without manual hassle?
2. Were the detected defects accurate?
3. Would you want this running as an automated PR check in CI?
