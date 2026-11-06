/**
 * Polyglot Browser Inspector (v1.2.0)
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
    requiresIntervention: 0,
    isScanning: false,
    elements: []
  };

  /**
   * Dynamic source locale detection from script attribute, <html lang>, meta tags or navigator.
   */
  function detectSourceLocale() {
    const fromAttr = scriptTag?.getAttribute('data-source-locale');
    if (fromAttr) return fromAttr;
    const htmlLang = document.documentElement.lang;
    if (htmlLang && htmlLang.trim().length > 0) return htmlLang.trim();
    const metaLang = document.querySelector('meta[name="language"]')?.getAttribute('content');
    if (metaLang && metaLang.trim().length > 0) return metaLang.trim();
    return navigator.language || 'en-US';
  }

  /**
   * Detects semantic element type to inform Polyglot Engine's layout heuristics.
   */
  function detectElementType(element) {
    const tag = element.tagName.toLowerCase();
    const role = element.getAttribute('role');
    const classes = String(element.className || '');

    if (tag === 'button' || role === 'button' || /btn|button/.test(classes)) {
      return 'button';
    }
    if (tag === 'nav' || role === 'navigation' || /nav|menu/.test(classes)) {
      return 'nav';
    }
    if (/^h[1-6]$/.test(tag)) {
      return 'heading';
    }
    if (tag === 'label') {
      return 'label';
    }
    return 'general';
  }

  /**
   * Explicit Text Node Selection Strategy:
   * 1. Check for developer explicit attribute [data-polyglot-text]
   * 2. Check for child element [data-polyglot-target]
   * 3. Prioritize direct child text nodes to preserve icons & nested elements
   * 4. Deep search excluding svgs, icons and tooltips
   */
  function findTargetTextNode(element) {
    // Strategy 1: Explicit data-polyglot-text attribute on target or container
    const explicitTextEl = element.querySelector('[data-polyglot-text]') || (element.hasAttribute('data-polyglot-text') ? element : null);
    if (explicitTextEl) {
      const walker = document.createTreeWalker(explicitTextEl, NodeFilter.SHOW_TEXT, null, false);
      let n;
      while ((n = walker.nextNode())) {
        if (n.textContent.trim().length > 0) return n;
      }
    }

    // Strategy 2: Explicit data-polyglot-target attribute
    const explicitTarget = element.querySelector('[data-polyglot-target]');
    if (explicitTarget) {
      const walker = document.createTreeWalker(explicitTarget, NodeFilter.SHOW_TEXT, null, false);
      let n;
      while ((n = walker.nextNode())) {
        if (n.textContent.trim().length > 0) return n;
      }
    }

    // Strategy 3: Direct child text nodes (avoids nested SVGs, badges, tooltips)
    for (let i = 0; i < element.childNodes.length; i++) {
      const child = element.childNodes[i];
      if (child.nodeType === Node.TEXT_NODE && child.textContent.trim().length > 0) {
        return child;
      }
    }

    // Strategy 4: Deep text walker, explicitly rejecting icons and non-text elements
    const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT, {
      acceptNode(node) {
        const parent = node.parentElement;
        if (!parent) return NodeFilter.FILTER_REJECT;
        const tag = parent.tagName.toLowerCase();
        if (tag === 'svg' || tag === 'path' || tag === 'i' || (tag === 'span' && parent.classList.contains('icon'))) {
          return NodeFilter.FILTER_REJECT;
        }
        return node.textContent.trim().length > 0 ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_SKIP;
      }
    }, false);

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
    const textNode = findTargetTextNode(element);
    return textNode ? textNode.textContent.trim() : (element.innerText || '').trim();
  }

  function safelyApplyText(element, newText) {
    const textNode = findTargetTextNode(element);
    if (textNode) {
      textNode.textContent = newText;
    } else {
      element.textContent = newText;
    }
  }

  /**
   * Scans adjacent/sibling interactive elements to detect bounding-box collisions
   * Filters out intentional overlaps (absolute/fixed positioning, aria-hidden, different z-index layers).
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
        // Filter out hidden, zero-opacity, or non-interactive background elements
        if (s.display === 'none' || s.visibility === 'hidden' || parseFloat(s.opacity) === 0 || s.pointerEvents === 'none') {
          return false;
        }
        // Filter out intentional absolute/fixed positioned badges or overlays
        if (s.position === 'absolute' || s.position === 'fixed') {
          return false;
        }
        // Filter out decorative or aria-hidden elements
        if (c.getAttribute('aria-hidden') === 'true' || c.getAttribute('role') === 'presentation' || c.getAttribute('role') === 'none') {
          return false;
        }
        if (c.closest('#polyglot-inspector-root')) return false;
        return true;
      });

      for (let i = 0; i < children.length; i++) {
        const r1 = children[i].getBoundingClientRect();
        if (r1.width <= 2 || r1.height <= 2) continue;

        for (let j = i + 1; j < children.length; j++) {
          const r2 = children[j].getBoundingClientRect();
          if (r2.width <= 2 || r2.height <= 2) continue;

          // Check for intentional distinct stacking contexts
          const s1 = window.getComputedStyle(children[i]);
          const s2 = window.getComputedStyle(children[j]);
          if (s1.zIndex !== s2.zIndex && s1.zIndex !== 'auto' && s2.zIndex !== 'auto') {
            continue;
          }

          // Check if bounding boxes collide along the inline axis (> 5px overlap)
          const overlapX = Math.max(0, Math.min(r1.right, r2.right) - Math.max(r1.left, r2.left));
          const overlapY = Math.max(0, Math.min(r1.bottom, r2.bottom) - Math.max(r1.top, r2.top));

          if (overlapX > 5 && overlapY > 5) {
            collisionCount++;
            children[i].style.outline = '2px dashed #ef4444';
            children[j].style.outline = '2px dashed #ef4444';
            children[i].setAttribute('title', '⚠️ Layout collision with sibling component');
            children[j].setAttribute('title', '⚠️ Layout collision with sibling component');
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

    const sourceLocale = detectSourceLocale();

    for (const item of inspectorState.elements) {
      const el = item.node;
      const text = item.originalText;
      const availableWidth = item.width || 140;
      const computed = window.getComputedStyle(el);
      const fontSize = parseFloat(computed.fontSize) || 14;
      const elemType = detectElementType(el);

      try {
        const res = await fetch(`${API_URL.replace(/\/$/, '')}/v1/localize`, {
          method: 'POST',
          headers,
          body: JSON.stringify({
            source_text: text,
            source_locale: sourceLocale,
            target_locales: [currentLocale],
            ui_context: {
              element_type: elemType,
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
              (el.scrollHeight > el.clientHeight + 1 && (computed.overflow === 'hidden' || computed.overflowY === 'hidden'));

            if (!stillOverflows) {
              el.style.outline = '2px solid #10b981'; // Green: verified fit
              el.setAttribute('title', `✅ Layout verified: fits in ${el.clientWidth}px container`);
              inspectorState.repairsApplied++;
            } else {
              // When container is too narrow even for ultra-compact text, flag for developer intervention
              inspectorState.requiresIntervention++;
              el.style.outline = '2px dashed #f97316'; // Orange: intervention required
              el.setAttribute('title', `⚠️ Developer intervention needed: container (${el.clientWidth}px) too narrow even for ultra-compact text (${el.scrollWidth}px). Expand container or adjust layout.`);
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
        <div style="display: flex; justify-content: space-between;">Needs Intervention: <strong id="poly-intervention" style="color: #f97316;">0</strong></div>
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
    const elIntervention = document.getElementById('poly-intervention');

    if (elScanned) elScanned.textContent = inspectorState.elementsScanned;
    if (elOverflows) elOverflows.textContent = inspectorState.overflowsDetected;
    if (elOverlaps) elOverlaps.textContent = inspectorState.overlapsDetected;
    if (elRepairs) elRepairs.textContent = inspectorState.repairsApplied;
    if (elIntervention) elIntervention.textContent = inspectorState.requiresIntervention;
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
