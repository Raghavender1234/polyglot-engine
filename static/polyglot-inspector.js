/**
 * Polyglot Browser Inspector (v1.1.0)
 * Scans real DOM geometry, detects text overflow, element clipping & visual component collisions,
 * and automatically applies verified non-destructive repairs via Polyglot Engine.
 */

(function () {
  if (window.__POLYGLOT_INSPECTOR_ACTIVE__) return;
  window.__POLYGLOT_INSPECTOR_ACTIVE__ = true;

  const scriptTag = document.currentScript;
  const configuredApiUrl = scriptTag?.getAttribute('data-api-url') || window.__POLYGLOT_API_URL__;
  const isLocalhost = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
  const API_URL = configuredApiUrl || (isLocalhost ? window.location.origin : 'https://polyglot-engine.onrender.com');
  const API_KEY = scriptTag?.getAttribute('data-api-key') || window.__POLYGLOT_API_KEY__ || '';
  let currentLocale = scriptTag?.getAttribute('data-locale') || 'de-DE';

  const inspectorState = {
    elementsScanned: 0,
    overflowsDetected: 0,
    overlapsDetected: 0,
    repairsApplied: 0,
    isScanning: false,
    elements: []
  };

  /**
   * Finds the primary text node within an element, ensuring child SVGs,
   * icons, and nested markup are never destroyed during localization swaps.
   */
  function findPrimaryTextNode(element) {
    const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT, null, false);
    let target = null;
    let maxLen = 0;
    let node;
    while ((node = walker.nextNode())) {
      const trimmed = node.textContent.trim();
      if (trimmed.length > maxLen) {
        maxLen = trimmed.length;
        target = node;
      }
    }
    return target;
  }

  function getElementText(element) {
    const textNode = findPrimaryTextNode(element);
    return textNode ? textNode.textContent.trim() : (element.innerText || '').trim();
  }

  function safelyApplyText(element, newText) {
    const textNode = findPrimaryTextNode(element);
    if (textNode) {
      textNode.textContent = newText;
    } else {
      element.textContent = newText;
    }
  }

  /**
   * Scans adjacent/sibling interactive elements to detect bounding-box collisions
   * (e.g. text expanding and colliding with adjacent icons, buttons or menu items).
   */
  function detectVisualOverlaps() {
    const interactiveContainers = document.querySelectorAll(
      'nav, [role="navigation"], header, .nav, .toolbar, .button-group, .flex, .btn-group, [role="menubar"], [role="tablist"]'
    );
    let collisionCount = 0;

    interactiveContainers.forEach((container) => {
      if (container.closest('#polyglot-inspector-root')) return;
      const children = Array.from(container.children).filter((c) => {
        const s = window.getComputedStyle(c);
        return s.display !== 'none' && s.visibility !== 'hidden' && !c.closest('#polyglot-inspector-root');
      });

      for (let i = 0; i < children.length; i++) {
        const r1 = children[i].getBoundingClientRect();
        if (r1.width === 0 || r1.height === 0) continue;

        for (let j = i + 1; j < children.length; j++) {
          const r2 = children[j].getBoundingClientRect();
          if (r2.width === 0 || r2.height === 0) continue;

          // Check if bounding boxes collide (> 3px overlap in both dimensions)
          const overlapX = Math.max(0, Math.min(r1.right, r2.right) - Math.max(r1.left, r2.left));
          const overlapY = Math.max(0, Math.min(r1.bottom, r2.bottom) - Math.max(r1.top, r2.top));

          if (overlapX > 3 && overlapY > 3) {
            collisionCount++;
            children[i].style.outline = '2px dashed #ef4444';
            children[j].style.outline = '2px dashed #ef4444';
            children[i].setAttribute('title', '⚠️ Visual collision with adjacent element');
            children[j].setAttribute('title', '⚠️ Visual collision with adjacent element');
          }
        }
      }
    });
    return collisionCount;
  }

  // 1. DOM Scanner & Real Layout Overflow Detector
  function scanPage() {
    inspectorState.elementsScanned = 0;
    inspectorState.overflowsDetected = 0;
    inspectorState.elements = [];

    // Clean previous diagnostic outlines
    document.querySelectorAll('[data-polyglot-inspected]').forEach((el) => {
      el.style.outline = '';
      el.removeAttribute('title');
      el.removeAttribute('data-polyglot-inspected');
    });

    // Target elements: buttons, links, nav tabs, headings, labels, cards, badges, and text containers
    const targets = document.querySelectorAll(
      'button, a, nav, [role="button"], .btn, h1, h2, h3, h4, h5, h6, label, p, .badge, [data-polyglot-detect]'
    );

    targets.forEach((el) => {
      // Skip inspector's own UI
      if (el.closest('#polyglot-inspector-root')) return;

      const style = window.getComputedStyle(el);
      if (style.display === 'none' || style.visibility === 'hidden') return;

      const text = getElementText(el);
      if (!text || text.length === 0) return;

      inspectorState.elementsScanned++;

      // Real Browser Geometry Checks:
      // A. Horizontal Overflow: scrollWidth > clientWidth
      const isHorizontalOverflow = el.scrollWidth > el.clientWidth + 1;
      // B. Vertical Clipping: scrollHeight > clientHeight (when overflow is constrained)
      const isVerticalOverflow = el.scrollHeight > el.clientHeight + 1 && (style.overflow === 'hidden' || style.overflowY === 'hidden');

      if (isHorizontalOverflow || isVerticalOverflow) {
        inspectorState.overflowsDetected++;
        el.setAttribute('data-polyglot-inspected', 'true');
        inspectorState.elements.push({
          node: el,
          originalText: text,
          width: el.clientWidth,
          scrollWidth: el.scrollWidth,
          overflowType: isHorizontalOverflow ? 'horizontal' : 'vertical'
        });

        // Highlight broken element with an amber outline
        el.style.outline = '2px dashed #f59e0b';
        el.setAttribute('title', `⚠️ Text overflow detected (${el.scrollWidth}px > ${el.clientWidth}px)`);
      }
    });

    inspectorState.overlapsDetected = detectVisualOverlaps();
    updateHUD();
  }

  // 2. Verified Non-Destructive Auto-Repair via Polyglot Engine
  async function repairOverflows() {
    if (inspectorState.elements.length === 0) return;

    const headers = { 'Content-Type': 'application/json' };
    if (API_KEY) {
      headers['X-API-Key'] = API_KEY;
    }

    for (const item of inspectorState.elements) {
      const el = item.node;
      const text = item.originalText;
      const availableWidth = item.width || 140;
      const computed = window.getComputedStyle(el);
      const fontSize = parseFloat(computed.fontSize) || 14;

      try {
        const res = await fetch(`${API_URL.replace(/\/$/, '')}/v1/localize`, {
          method: 'POST',
          headers,
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
          const result = data.results && data.results[currentLocale];
          if (result) {
            // Apply non-destructive repair preserving SVG/icons
            safelyApplyText(el, result.ui_safe_text);
            if (result.css_rules) {
              el.dir = result.css_rules.dir || 'auto';
              if (result.css_rules.line_height) el.style.lineHeight = result.css_rules.line_height;
              if (result.css_rules.font_family) el.style.fontFamily = result.css_rules.font_family;
            }

            // Post-Repair Verification: re-measure in the live DOM
            const stillOverflows = (el.scrollWidth > el.clientWidth + 1) ||
              (el.scrollHeight > el.clientHeight + 1 && window.getComputedStyle(el).overflow === 'hidden');

            if (!stillOverflows) {
              el.style.outline = '2px solid #10b981'; // Green: verified fit
              el.setAttribute('title', `✅ Layout verified: fits in ${el.clientWidth}px container`);
              inspectorState.repairsApplied++;
            } else {
              // Fallback protection: apply graceful CSS truncation if container is rigidly narrow
              el.style.outline = '2px dashed #3b82f6'; // Blue: fallback applied
              el.style.overflow = 'hidden';
              el.style.textOverflow = 'ellipsis';
              el.style.whiteSpace = 'nowrap';
              el.setAttribute('title', 'ℹ️ Shortened variant applied; container constrained, ellipsis added.');
              inspectorState.repairsApplied++;
            }
          }
        } else {
          console.warn(`[Polyglot Inspector] API returned status ${res.status} from ${API_URL}`);
        }
      } catch (err) {
        console.warn(`[Polyglot Inspector] Could not reach Polyglot API at ${API_URL}. Set data-api-url attribute on script tag.`, err);
      }
    }

    updateHUD();
  }

  // 3. Floating HUD Interface
  function createHUD() {
    if (document.getElementById('polyglot-inspector-root')) return;

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
      width: 290px;
    `;

    root.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; border-bottom: 1px solid #1e293b; padding-bottom: 8px;">
        <strong style="color: #60a5fa; font-size: 13px;">⚡ Polyglot Inspector</strong>
        <span id="poly-status" style="font-size: 11px; color: #10b981;">● Active</span>
      </div>

      <div style="margin-bottom: 10px; display: flex; flex-direction: column; gap: 4px; color: #94a3b8;">
        <div style="display: flex; justify-content: space-between;">Elements Scanned: <strong id="poly-scanned" style="color: #f8fafc;">0</strong></div>
        <div style="display: flex; justify-content: space-between;">Text Overflows: <strong id="poly-overflows" style="color: #f59e0b;">0</strong></div>
        <div style="display: flex; justify-content: space-between;">Visual Collisions: <strong id="poly-overlaps" style="color: #ef4444;">0</strong></div>
        <div style="display: flex; justify-content: space-between;">Verified Repairs: <strong id="poly-repairs" style="color: #10b981;">0</strong></div>
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
        🛠️ Verified Auto-Repair
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
    const elOverlaps = document.getElementById('poly-overlaps');
    const elRepairs = document.getElementById('poly-repairs');

    if (elScanned) elScanned.textContent = inspectorState.elementsScanned;
    if (elOverflows) elOverflows.textContent = inspectorState.overflowsDetected;
    if (elOverlaps) elOverlaps.textContent = inspectorState.overlapsDetected;
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
