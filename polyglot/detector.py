"""
Polyglot Detector — Full-Page Collision & Container Overflow Detection
Compares translated elements against ALL visible elements on the page (not just the translated subset),
using stable integer element pair keys and intelligent filtering for intentional badges and overlays.
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

            overflows.push({
                id: el.getAttribute('data-polyglot-id'),
                tag: el.tagName.toLowerCase(),
                selector: getStableSelector(el),
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

    // 2. Discover ALL visible elements across the entire page
    const allCandidates = document.querySelectorAll(
        'button, a, input, select, textarea, [role="button"], [role="tab"], [role="menuitem"], p, span, h1, h2, h3, h4, h5, h6, [role="row"], td, th, img, svg, nav, header, aside, .badge, .btn, [class*="item"], [class*="card"], [class*="btn"], [class*="link"]'
    );
    const visibleElements = [];

    for (let i = 0; i < allCandidates.length; i++) {
        const el = allCandidates[i];
        if (el.closest('#polyglot-inspector-root')) continue;
        const style = window.getComputedStyle(el);
        if (style.display === 'none' || style.visibility === 'hidden' || parseFloat(style.opacity) === 0) continue;
        if (style.pointerEvents === 'none') continue;

        const r = el.getBoundingClientRect();
        if (r.width <= 4 || r.height <= 4) continue;

        // Skip full-screen backdrops / overlays
        if (r.width >= window.innerWidth * 0.95 && r.height >= window.innerHeight * 0.95) continue;

        const isBadgeOrOverlay = (
            el.getAttribute('role') === 'status' ||
            el.getAttribute('aria-hidden') === 'true' ||
            (typeof el.className === 'string' && /(badge|counter|avatar-status|tooltip|indicator|dot|pill-status)/i.test(el.className))
        );

        visibleElements.push({
            uid: i,
            el: el,
            rect: r,
            style: style,
            isTranslated: el.hasAttribute('data-polyglot-id') && targetIds.has(el.getAttribute('data-polyglot-id')),
            text: (el.innerText || el.textContent || '').trim().substring(0, 40),
            tag: el.tagName.toLowerCase(),
            selector: getStableSelector(el),
            isBadge: isBadgeOrOverlay,
            isInteractive: /^(button|a|input|select|textarea)$/i.test(el.tagName) || el.getAttribute('role') === 'button'
        });
    }

    // 3. Collision Evaluation: Compare translated elements against all visible elements
    // Uses integer UIDs so distinct elements are NEVER falsely skipped by string casting!
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
        overflows: overflows,
        collisions: collisions
    };
}
"""

class CollisionDetector:
    @staticmethod
    def detect(page, target_ids: List[str]) -> Dict[str, Any]:
        return page.evaluate(JS_DETECT_FULLPAGE_COLLISIONS, {"targetIds": target_ids})
