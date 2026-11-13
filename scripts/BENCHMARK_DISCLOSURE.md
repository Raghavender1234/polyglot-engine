# Polyglot Engine: Benchmark Architecture & Accuracy Disclosures

Polyglot Engine maintains two distinct testing suites to evaluate reliability. This document explicitly defines the boundaries, backends, test counts, and verified metrics for each suite so that deterministic browser layout testing is never conflated with machine learning vision inference.

---

## 1. Ground-Truth Layout & BiDi Benchmark (Deterministic DOM Engine)
- **File:** [`benchmarks/test_60_case_benchmark.py`](../benchmarks/test_60_case_benchmark.py)
- **Engine Evaluated:** Playwright DOM Reflow & Collision Detector (`polyglot.detector.CollisionDetector`)
- **Backend:** Chromium Headless (Physical CSS bounding box calculations, `scrollWidth`/`clientWidth` reflow, and BiDi directional isolation verification)
- **Total Test Cases:** **60 Ground-Truth Test Cases**
  - **40 Real Defect Cases:**
    - 10 German Compound Word Rigid-Width Overflows
    - 10 Arabic/Hebrew BiDi Inversions & Directional Spills
    - 10 Japanese Rigid-Width Vertical & Horizontal Truncations
    - 10 Physical Button & Navigation Collisions (Negative Margin / Flex Sibling Collisions)
  - **20 Clean Controls (Negative Controls — Must NOT Flag):**
    - 5 Properly Isolated Arabic Currency Strings (`<bdi>` & Unicode Isolate)
    - 5 Cleanly Wrapped Multi-Line Containers (`flex-wrap: wrap`)
    - 5 Legitimate Floating Badges (Filtered out via badge heuristics)
    - 5 Standard Unconstrained Flexible Action Buttons
- **Measured Metrics:**
  - **True Positives (TP):** 40 / 40
  - **False Positives (FP):** 0 / 20
  - **False Negatives (FN):** 0 / 40
  - **True Negatives (TN):** 20 / 20
  - **Precision:** 100.0%
  - **Recall:** 100.0%
  - **False Positive Rate:** 0.0%

---

## 2. Moondream Vision Language Model (VLM) Benchmark
- **File:** [`scripts/benchmark_moondream.py`](benchmark_moondream.py)
- **Engine Evaluated:** Moondream 2 & 3.1 VLM (Layer 2 Visual Verification Layer)
- **Supported Backends:**
  1. `ollama`: Strictly local inference on `127.0.0.1:11434` (requires `ollama run moondream`).
  2. `moondream3_api`: Explicitly opt-in cloud API (`https://api.moondream.ai/v1/query`).
  3. `mock`: Deterministic offline test adapter for CI pipeline execution and structure verification.
- **Total Test Cases:** **50 Synthetic Image Crop Cases**
  - 10 Text Clipping & Container Overflow Crops
  - 10 Text & Icon Physical Overlap Crops
  - 10 Bidirectional (BiDi) & Currency Inversion Crops
  - 10 Font Illegibility & Sizing Degradation Crops
  - 10 Clean Control Crops (Legitimate multi-line wraps, floating counters, tone marks)

> [!IMPORTANT]
> **Honest Evaluation Disclosure:**
> When `--backend mock` is used, the script simulates predictions for pipeline integrity testing. **Mock results do not represent actual neural model accuracy.** Real vision accuracy must be measured exclusively with `--backend ollama` or `--backend moondream3_api`.
