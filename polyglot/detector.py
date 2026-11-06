"""
Polyglot Detector — Full-Page Collision & Container Overflow Detection
Compares translated elements against ALL visible elements on the page (not just the translated subset),
while filtering legitimate overlays, background layers, and ancestor-child containment.
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

    // 1. Check Container Overflows on Translated Elements
    for (const el of translatedEls) {
        const style = window.getComputedStyle(el);
        const isHorizOverflow = el.scrollWidth > el.clientWidth + 1;
        const isVertOverflow = el.scrollHeight > el.clientHeight + 1 &&
            (style.overflow === 'hidden' || style.overflowY === 'hidden' || style.overflow === 'clip');

        if (isHorizOverflow || isVertOverflow) {
            overflows.push({
                id: el.getAttribute('data-polyglot-id'),
                tag: el.tagName.toLowerCase(),
                selector: el.id ? '#' + el.id : (el.getAttribute('data-testid') ? `[data-testid="${el.getAttribute('data-testid')}"]` : el.tagName.toLowerCase()),
                text: (el.innerText || el.textContent || '').trim().substring(0, 40),
                scrollWidth: el.scrollWidth,
                clientWidth: el.clientWidth,
                overflowPx: Math.max(el.scrollWidth - el.clientWidth, el.scrollHeight - el.clientHeight)
            });
        }
    }

    // 2. Discover ALL visible elements across the entire page (icons, untranslated text, sidebars, buttons, links)
    const allCandidates = document.querySelectorAll(
        'button, a, input, select, textarea, [role="button"], [role="tab"], p, span, h1, h2, h3, h4, h5, h6, [role="row"], td, th, img, svg, nav, header, aside, .badge, .btn'
    );
    const visibleElements = [];

    for (const el of allCandidates) {
        if (el.closest('#polyglot-inspector-root')) continue;
        const style = window.getComputedStyle(el);
        if (style.display === 'none' || style.visibility === 'hidden' || parseFloat(style.opacity) === 0) continue;
        if (style.pointerEvents === 'none') continue;

        const r = el.getBoundingClientRect();
        if (r.width <= 4 || r.height <= 4) continue;

        // Skip full-screen backdrops / overlays
        if (r.width >= window.innerWidth * 0.95 && r.height >= window.innerHeight * 0.95) continue;

        visibleElements.push({
            el: el,
            rect: r,
            isTranslated: el.hasAttribute('data-polyglot-id') && targetIds.has(el.getAttribute('data-polyglot-id')),
            text: (el.innerText || el.textContent || '').trim().substring(0, 35),
            tag: el.tagName.toLowerCase(),
            selector: el.id ? '#' + el.id : (el.getAttribute('data-testid') ? `[data-testid="${el.getAttribute('data-testid')}"]` : el.tagName.toLowerCase())
        });
    }

    // 3. Collision Evaluation: Every translated element compared against EVERY visible element on the page
    const checkedPairs = new Set();

    for (const item1 of visibleElements) {
        if (!item1.isTranslated) continue; // Only test intersections where at least one element is translated

        for (const item2 of visibleElements) {
            if (item1.el === item2.el) continue;

            const pairKey = [item1.el, item2.el].sort().toString();
            if (checkedPairs.has(pairKey)) continue;
            checkedPairs.add(pairKey);

            // Filter ancestor-descendant containment
            if (item1.el.contains(item2.el) || item2.el.contains(item1.el)) continue;

            const r1 = item1.rect;
            const r2 = item2.rect;

            // Bounding box collision calculation
            const overlapX = Math.max(0, Math.min(r1.right, r2.right) - Math.max(r1.left, r2.left));
            const overlapY = Math.max(0, Math.min(r1.bottom, r2.bottom) - Math.max(r1.top, r2.top));

            // Genuine collision: significant overlap in both dimensions (>4px)
            if (overlapX > 4 && overlapY > 4) {
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
                    overlapY: Math.round(overlapY)
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
