/**
 * Polyglot Browser Inspector (v1.0.0)
 * Scans real DOM geometry, detects text overflow & element clipping,
 * and automatically repairs broken UI components via Polyglot Engine.
 */

(function () {
  if (window.__POLYGLOT_INSPECTOR_ACTIVE__) return;
  window.__POLYGLOT_INSPECTOR_ACTIVE__ = true;

  const API_URL = document.currentScript?.getAttribute('data-api-url') || window.location.origin;
  let currentLocale = document.currentScript?.getAttribute('data-locale') || 'de-DE';

  const inspectorState = {
    elementsScanned: 0,
    overflowsDetected: 0,
    repairsApplied: 0,
    isScanning: false,
    elements: []
  };

  // 1. DOM Scanner & Overflow Detector
  function scanPage() {
    inspectorState.elementsScanned = 0;
    inspectorState.overflowsDetected = 0;
    inspectorState.elements = [];

    // Target elements: buttons, links, nav tabs, headings, labels
    const targets = document.querySelectorAll('button, a, nav, [role="button"], .btn, h1, h2, h3, h4, label');

    targets.forEach((el) => {
      // Skip inspector's own UI
      if (el.closest('#polyglot-inspector-root')) return;

      const style = window.getComputedStyle(el);
      if (style.display === 'none' || style.visibility === 'hidden') return;

      inspectorState.elementsScanned++;

      // Real Browser Geometry Checks:
      // A. Horizontal Overflow: scrollWidth > clientWidth
      const isHorizontalOverflow = el.scrollWidth > el.clientWidth + 1;
      // B. Vertical Clipping: scrollHeight > clientHeight
      const isVerticalOverflow = el.scrollHeight > el.clientHeight + 1 && style.overflow === 'hidden';

      if (isHorizontalOverflow || isVerticalOverflow) {
        inspectorState.overflowsDetected++;
        inspectorState.elements.push({
          node: el,
          originalText: el.innerText.trim(),
          width: el.clientWidth,
          scrollWidth: el.scrollWidth,
          overflowType: isHorizontalOverflow ? 'horizontal' : 'vertical'
        });

        // Highlight broken element with an amber outline
        el.style.outline = '2px dashed #f59e0b';
      }
    });

    updateHUD();
  }

  // 2. Automatic Repair via Polyglot Engine
  async function repairOverflows() {
    if (inspectorState.elements.length === 0) return;

    for (const item of inspectorState.elements) {
      const el = item.node;
      const text = item.originalText;
      const availableWidth = item.width || 140;
      const computed = window.getComputedStyle(el);
      const fontSize = parseFloat(computed.fontSize) || 14;

      try {
        const res = await fetch(`${API_URL.replace(/\/$/, '')}/v1/localize`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            source_text: text,
            source_locale: 'en-US',
            target_locales: [currentLocale],
            ui_context: {
              element_type: 'button',
              max_width_px: availableWidth,
              font_size_px: fontSize,
              font_weight: 500
            }
          })
        });

        if (res.ok) {
          const data = await res.json();
          const result = data.results[currentLocale];
          if (result) {
            // Apply safe repair
            el.innerText = result.ui_safe_text;
            el.dir = result.css_rules.dir;
            el.style.lineHeight = result.css_rules.line_height;
            el.style.fontFamily = result.css_rules.font_family;
            el.style.outline = '2px solid #10b981'; // Green outline = repaired

            inspectorState.repairsApplied++;
          }
        }
      } catch (err) {
        console.warn('[Polyglot Inspector] Repair failed for:', text, err);
      }
    }

    updateHUD();
  }

  // 3. Floating HUD Interface
  function createHUD() {
    const root = document.createElement('div');
    root.id = 'polyglot-inspector-root';
    root.style.cssText = `
      position: fixed;
      bottom: 20px;
      right: 20px;
      z-index: 999999;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      font-size: 12px;
      background: #0f172a;
      color: #f8fafc;
      border: 1px solid #334155;
      border-radius: 12px;
      padding: 14px;
      box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);
      width: 280px;
    `;

    root.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; border-bottom: 1px solid #1e293b; padding-bottom: 8px;">
        <strong style="color: #60a5fa; font-size: 13px;">⚡ Polyglot Inspector</strong>
        <span id="poly-status" style="font-size: 11px; color: #10b981;">● Active</span>
      </div>

      <div style="margin-bottom: 10px; display: flex; flex-direction: column; gap: 4px; color: #94a3b8;">
        <div>Elements Scanned: <strong id="poly-scanned" style="color: #f8fafc;">0</strong></div>
        <div>Overflows Detected: <strong id="poly-overflows" style="color: #f59e0b;">0</strong></div>
        <div>Repairs Applied: <strong id="poly-repairs" style="color: #10b981;">0</strong></div>
      </div>

      <div style="display: flex; gap: 6px; margin-bottom: 10px;">
        <select id="poly-locale" style="flex: 1; background: #1e293b; color: white; border: 1px solid #334155; border-radius: 6px; padding: 4px 6px; font-size: 11px;">
          <option value="de-DE">German (de-DE)</option>
          <option value="ur-PK">Urdu (ur-PK)</option>
          <option value="ar-SA">Arabic (ar-SA)</option>
          <option value="ja-JP">Japanese (ja-JP)</option>
        </select>
        <button id="poly-scan-btn" style="background: #3b82f6; color: white; border: none; border-radius: 6px; padding: 4px 10px; font-weight: 600; cursor: pointer;">Scan</button>
      </div>

      <button id="poly-repair-btn" style="width: 100%; background: #10b981; color: white; border: none; border-radius: 6px; padding: 6px; font-weight: 600; cursor: pointer;">
        🛠️ Auto-Repair Overflows
      </button>
    `;

    document.body.appendChild(root);

    document.getElementById('poly-scan-btn').addEventListener('click', scanPage);
    document.getElementById('poly-repair-btn').addEventListener('click', repairOverflows);
    document.getElementById('poly-locale').addEventListener('change', (e) => {
      currentLocale = e.target.value;
      scanPage();
    });
  }

  function updateHUD() {
    const elScanned = document.getElementById('poly-scanned');
    const elOverflows = document.getElementById('poly-overflows');
    const elRepairs = document.getElementById('poly-repairs');

    if (elScanned) elScanned.textContent = inspectorState.elementsScanned;
    if (elOverflows) elOverflows.textContent = inspectorState.overflowsDetected;
    if (elRepairs) elRepairs.textContent = inspectorState.repairsApplied;
  }

  // Initialize on load
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      createHUD();
      scanPage();
    });
  } else {
    createHUD();
    scanPage();
  }
})();
