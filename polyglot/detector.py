"""
Polyglot Detector — Full-Page Collision, Container Overflow & In-Browser BiDi Detection
Compares translated elements against ALL visible elements on the page (not just the translated subset),
uses stable integer element pair keys, evaluates genuine in-browser BiDi directional/isolation defects,
and applies intelligent filtering for intentional badges, icons, and overlays.
"""

from typing import Dict, Any, List

JS_DETECT_FULLPAGE_COLLISIONS = """
(payload) => {
    const targetIds = new Set(payload.targetIds || []);
    const translatedEls = [];
    document.querySelectorAll('[data-polyglot-id]').forEach(el => {
        const id = el.getAttribute('data-polyglot-id');
        if (targetIds.has(id)) {
            translatedEls.push(el);
        }
    });

    const overflows = [];
    const collisions = [];
    const bidiIssues = [];

    // Helper: Build stable selector
    function getStableSelector(el) {
        if (el.id) return '#' + el.id;
        const testId = el.getAttribute('data-testid') || el.getAttribute('data-test');
        if (testId) return `[data-testid="${testId}"]`;
        const ariaLabel = el.getAttribute('aria-label');
        if (ariaLabel) return `${el.tagName.toLowerCase()}[aria-label="${ariaLabel}"]`;
        const role = el.getAttribute('role');
        if (role) return `${el.tagName.toLowerCase()}[role="${role}"]`;
        if (el.className && typeof el.className === 'string') {
            const classes = el.className.trim().split(/\\s+/).filter(c => c.length > 2 && !c.startsWith('css-'));
            if (classes.length > 0) return `.${classes[0]}`;
        }
        return el.tagName.toLowerCase();
    }

    // Helper: Locate responsible source stylesheet in document.styleSheets
    function findRuleSourceSheet(selector) {
        if (!selector) return null;
        try {
            for (let i = 0; i < document.styleSheets.length; i++) {
                const sheet = document.styleSheets[i];
                const href = sheet.href;
                if (!href) continue;
                let rules;
                try {
                    rules = sheet.cssRules || sheet.rules;
                } catch(e) {
                    continue;
                }
                if (!rules) continue;
                for (let j = 0; j < rules.length; j++) {
                    const r = rules[j];
                    if (r.selectorText && (r.selectorText === selector || r.selectorText.includes(selector))) {
                        try {
                            const u = new URL(href, window.location.href);
                            return u.pathname.split('/').pop();
                        } catch(e) {
                            return href.split('/').pop().split('?')[0];
                        }
                    }
                }
            }
        } catch(e) {}
        return null;
    }

    // 1. Check Container Overflows on Translated Elements with fresh computed styles
    for (const el of translatedEls) {
        const style = window.getComputedStyle(el);
        const isHorizOverflow = el.scrollWidth > el.clientWidth + 1;
        const isVertOverflow = el.scrollHeight > el.clientHeight + 1 &&
            (style.overflow === 'hidden' || style.overflowY === 'hidden' || style.overflow === 'clip');

        if (isHorizOverflow || isVertOverflow) {
            const parent = el.parentElement;
            const parentStyle = parent ? window.getComputedStyle(parent) : null;
            const parentRect = parent ? parent.getBoundingClientRect() : null;
            const sel = getStableSelector(el);

            overflows.push({
                id: el.getAttribute('data-polyglot-id'),
                tag: el.tagName.toLowerCase(),
                selector: sel,
                target_stylesheet: findRuleSourceSheet(sel),
                text: (el.innerText || el.textContent || '').trim().substring(0, 50),
                scrollWidth: el.scrollWidth,
                clientWidth: el.clientWidth,
                scrollHeight: el.scrollHeight,
                clientHeight: el.clientHeight,
                overflowPx: Math.max(el.scrollWidth - el.clientWidth, el.scrollHeight - el.clientHeight),
                computedWidth: parseFloat(style.width) || el.clientWidth,
                computedMaxWidth: style.maxWidth,
                whiteSpace: style.whiteSpace,
                flexShrink: style.flexShrink,
                parentTag: parent ? parent.tagName.toLowerCase() : '',
                parentDisplay: parentStyle ? parentStyle.display : '',
                parentFlexWrap: parentStyle ? parentStyle.flexWrap : '',
                parentWidth: parentRect ? parentRect.width : 0
            });
        }
    }

    // 2. Visual BiDi Directional & Isolation Defects (Zero False Positives)
    for (const el of translatedEls) {
        const text = (el.innerText || el.textContent || '').trim();
        const hasRtlChars = /[\\u0600-\\u06FF\\u0750-\\u077F\\u0590-\\u05FF]/.test(text);
        if (!hasRtlChars) continue;

        const style = window.getComputedStyle(el);
        const isRtlContext = (el.dir === 'rtl' || style.direction === 'rtl' || Boolean(el.closest('[dir="rtl"]')));

        // Check if explicitly isolated
        const hasExplicitIsolate = (
            style.unicodeBidi === 'isolate' ||
            style.unicodeBidi === 'isolate-override' ||
            style.unicodeBidi === 'plaintext' ||
            /[\\u2066\\u2067\\u2068]/.test(text) ||
            el.tagName.toLowerCase() === 'bdi' ||
            Boolean(el.querySelector('bdi'))
        );

        let defectDetected = null;

        // Check A: Visual Currency/Number Symbol Inversion
        const numMatch = text.match(/([\\$€£¥#\\+\\-])\\s*(\\d+[\\d\\.,]*)/);
        if (numMatch) {
            const symbol = numMatch[1];
            const numPart = numMatch[2];

            try {
                const range = document.createRange();
                const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
                let node;
                let symRect = null, numRect = null;

                while ((node = walker.nextNode())) {
                    const cText = node.textContent;
                    const symIdx = cText.indexOf(symbol);
                    const numIdx = cText.indexOf(numPart);

                    if (symIdx !== -1 && symRect === null) {
                        range.setStart(node, symIdx);
                        range.setEnd(node, symIdx + 1);
                        symRect = range.getBoundingClientRect();
                    }
                    if (numIdx !== -1 && numRect === null) {
                        range.setStart(node, numIdx);
                        range.setEnd(node, numIdx + 1);
                        numRect = range.getBoundingClientRect();
                    }
                }

                // If symbol is visually placed to the RIGHT of the number in LTR context,
                // the symbol was inverted by BiDi algorithm!
                if (symRect && numRect && symRect.width > 0 && numRect.width > 0) {
                    if (symRect.left > numRect.right + 2) {
                        defectDetected = {
                            type: 'CURRENCY_SYMBOL_INVERSION',
                            explanation: `Currency symbol '${symbol}' visually flipped to the wrong side of '${numPart}' due to un-isolated mixed-direction rendering.`,
                            remedy: 'Isolate the embedded directional run using Unicode isolate marks or <bdi> tag.'
                        };
                    }
                }
            } catch(e) {}
        }

        // Check B: Neutral punctuation spill in LTR container
        if (!defectDetected && !isRtlContext && !hasExplicitIsolate) {
            const trailingPunctMatch = text.match(/([:!?.])\\s*$/);
            if (trailingPunctMatch) {
                const punctChar = trailingPunctMatch[1];
                try {
                    const range = document.createRange();
                    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
                    let node;
                    let punctRect = null, firstRtlRect = null;

                    while ((node = walker.nextNode())) {
                        const cText = node.textContent;
                        for (let k = 0; k < cText.length; k++) {
                            const c = cText[k];
                            if (firstRtlRect === null && /[\\u0600-\\u06FF\\u0750-\\u077F\\u0590-\\u05FF]/.test(c)) {
                                range.setStart(node, k);
                                range.setEnd(node, k + 1);
                                firstRtlRect = range.getBoundingClientRect();
                            }
                        }
                        const pIdx = cText.lastIndexOf(punctChar);
                        if (pIdx !== -1 && punctRect === null) {
                            range.setStart(node, pIdx);
                            range.setEnd(node, pIdx + 1);
                            punctRect = range.getBoundingClientRect();
                        }
                    }

                    if (punctRect && firstRtlRect && punctRect.right < firstRtlRect.left) {
                        defectDetected = {
                            type: 'NEUTRAL_PUNCTUATION_SPILL',
                            explanation: `Trailing punctuation '${punctChar}' spilled to the opposite visual boundary because element lacks directional context or isolation.`,
                            remedy: 'Apply dir="auto" or wrap the string in Unicode isolate marks.'
                        };
                    }
                } catch(e) {}
            }
        }

        if (defectDetected) {
            const sel = getStableSelector(el);
            bidiIssues.push({
                id: el.getAttribute('data-polyglot-id'),
                tag: el.tagName.toLowerCase(),
                selector: sel,
                text: text.substring(0, 50),
                target_stylesheet: findRuleSourceSheet(sel),
                category: 'BIDI_DIRECTIONAL_ISOLATION',
                type: defectDetected.type,
                explanation: defectDetected.explanation,
                remedy: defectDetected.remedy
            });
        }
    }

    // 3. Discover ALL visible elements across the entire page (custom elements, widgets, containers, buttons, etc.)
    const allDomNodes = document.body ? document.body.querySelectorAll('*') : [];
    const visibleElements = [];
    const NON_OBSTACLE_TAGS = new Set([
        'script', 'style', 'noscript', 'template', 'meta', 'link', 'br', 'hr', 'source', 'track'
    ]);

    for (let i = 0; i < allDomNodes.length; i++) {
        const el = allDomNodes[i];
        if (el.closest('#polyglot-inspector-root')) continue;
        const tag = el.tagName.toLowerCase();
        if (NON_OBSTACLE_TAGS.has(tag)) continue;

        const style = window.getComputedStyle(el);
        if (style.display === 'none' || style.visibility === 'hidden' || parseFloat(style.opacity) === 0) continue;
        if (style.pointerEvents === 'none') continue;

        const r = el.getBoundingClientRect();
        if (r.width <= 4 || r.height <= 4) continue;

        // Skip full-screen backdrops / overlays
        if (r.width >= window.innerWidth * 0.96 && r.height >= window.innerHeight * 0.96) continue;

        // Visual obstacle check: must have direct text, be a leaf element, be interactive, or have visible background/border
        const hasDirectText = Array.from(el.childNodes).some(n => n.nodeType === Node.TEXT_NODE && n.textContent.trim().length > 0);
        const isLeaf = el.children.length === 0;
        const hasPaint = (
            (style.backgroundColor !== 'rgba(0, 0, 0, 0)' && style.backgroundColor !== 'transparent') ||
            (parseFloat(style.borderWidth) > 0 && style.borderStyle !== 'none') ||
            style.backgroundImage !== 'none' ||
            style.boxShadow !== 'none'
        );
        const isInteractive = /^(button|a|input|select|textarea|summary|details)$/i.test(tag) ||
            el.getAttribute('role') === 'button' ||
            el.getAttribute('role') === 'tab' ||
            el.getAttribute('role') === 'menuitem';

        if (!hasDirectText && !isLeaf && !hasPaint && !isInteractive) {
            continue;
        }

        const isBadgeOrOverlay = (
            el.getAttribute('role') === 'status' ||
            el.getAttribute('aria-hidden') === 'true' ||
            (typeof el.className === 'string' && /(badge|counter|avatar-status|tooltip|indicator|dot|pill-status)/i.test(el.className))
        );

        visibleElements.push({
            uid: visibleElements.length,
            el: el,
            rect: r,
            style: style,
            isTranslated: el.hasAttribute('data-polyglot-id') && targetIds.has(el.getAttribute('data-polyglot-id')),
            text: (el.innerText || el.textContent || '').trim().substring(0, 40),
            tag: tag,
            selector: getStableSelector(el),
            isBadge: isBadgeOrOverlay,
            isInteractive: isInteractive
        });
    }

    // 4. Collision Evaluation: Compare translated elements against all visible elements
    const checkedPairs = new Set();

    for (let i = 0; i < visibleElements.length; i++) {
        const item1 = visibleElements[i];
        if (!item1.isTranslated) continue;

        for (let j = 0; j < visibleElements.length; j++) {
            if (i === j) continue;
            const item2 = visibleElements[j];

            const pairKey = item1.uid < item2.uid ? (item1.uid + ':' + item2.uid) : (item2.uid + ':' + item1.uid);
            if (checkedPairs.has(pairKey)) continue;
            checkedPairs.add(pairKey);

            // Filter ancestor-descendant containment
            if (item1.el.contains(item2.el) || item2.el.contains(item1.el)) continue;

            // Filter intentional floating badges/counters nestled inside a parent container
            if (item1.isBadge || item2.isBadge) continue;

            const r1 = item1.rect;
            const r2 = item2.rect;

            // Bounding box collision calculation
            const overlapX = Math.max(0, Math.min(r1.right, r2.right) - Math.max(r1.left, r2.left));
            const overlapY = Math.max(0, Math.min(r1.bottom, r2.bottom) - Math.max(r1.top, r2.top));

            // Genuine collision: significant physical overlap in both dimensions (>4px)
            if (overlapX > 4 && overlapY > 4) {
                const area1 = r1.width * r1.height;
                const area2 = r2.width * r2.height;
                const overlapArea = overlapX * overlapY;
                const minArea = Math.min(area1, area2);

                // Filter nested decorative icons/glyphs inside interactive controls
                const isIcon1 = /^(svg|path|i|img)$/i.test(item1.tag) || (typeof item1.el.className === 'string' && /(icon|glyph|avatar|symbol)/i.test(item1.el.className));
                const isIcon2 = /^(svg|path|i|img)$/i.test(item2.tag) || (typeof item2.el.className === 'string' && /(icon|glyph|avatar|symbol)/i.test(item2.el.className));
                if ((isIcon1 || isIcon2) && (overlapArea / minArea > 0.75)) continue;

                // Filter fixed/sticky headers overlapping background scrolled elements
                const isFixed1 = item1.style.position === 'fixed' || item1.style.position === 'sticky';
                const isFixed2 = item2.style.position === 'fixed' || item2.style.position === 'sticky';
                if ((isFixed1 !== isFixed2) && (item1.el.parentElement !== item2.el.parentElement)) continue;

                const parent1 = item1.el.parentElement;
                const parentStyle1 = parent1 ? window.getComputedStyle(parent1) : null;

                collisions.push({
                    translatedId: item1.el.getAttribute('data-polyglot-id'),
                    otherTranslatedId: item2.isTranslated ? item2.el.getAttribute('data-polyglot-id') : null,
                    elem1: item1.tag,
                    text1: item1.text,
                    selector1: item1.selector,
                    elem2: item2.tag,
                    text2: item2.text,
                    selector2: item2.selector,
                    isOtherTranslated: item2.isTranslated,
                    overlapArea: Math.round(overlapX * overlapY),
                    overlapX: Math.round(overlapX),
                    overlapY: Math.round(overlapY),
                    parentDisplay: parentStyle1 ? parentStyle1.display : '',
                    parentFlexWrap: parentStyle1 ? parentStyle1.flexWrap : ''
                });
            }
        }
    }

    return {
        overflowCount: overflows.length,
        collisionCount: collisions.length,
        bidiCount: bidiIssues.length,
        totalDefects: overflows.length + collisions.length + bidiIssues.length,
        overflows: overflows,
        collisions: collisions,
        bidiIssues: bidiIssues
    };
}
"""

class CollisionDetector:
    @staticmethod
    def detect(page, target_ids: List[str]) -> Dict[str, Any]:
        return page.evaluate(JS_DETECT_FULLPAGE_COLLISIONS, {"targetIds": target_ids})
