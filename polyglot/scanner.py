"""
Polyglot Scanner — DOM Element Discovery & Geometry Inspection
Extracts interactive and text elements while deduplicating nested targets and resolving robust selectors.
"""

from typing import Dict, Any, List

JS_DISCOVER_ELEMENTS = """
() => {
    function findTargetTextNode(element) {
        const explicitTextEl = element.querySelector('[data-polyglot-text]') || (element.hasAttribute('data-polyglot-text') ? element : null);
        if (explicitTextEl) {
            const walker = document.createTreeWalker(explicitTextEl, NodeFilter.SHOW_TEXT, null, false);
            let n;
            while ((n = walker.nextNode())) {
                if (n.textContent.trim().length > 0) return n;
            }
        }
        for (let i = 0; i < element.childNodes.length; i++) {
            const child = element.childNodes[i];
            if (child.nodeType === Node.TEXT_NODE && child.textContent.trim().length > 0) return child;
        }
        const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT, {
            acceptNode(node) {
                const parent = node.parentElement;
                if (!parent) return NodeFilter.FILTER_REJECT;
                const tag = parent.tagName.toLowerCase();
                if (tag === 'svg' || tag === 'path' || tag === 'i' || tag === 'script' || tag === 'style') return NodeFilter.FILTER_REJECT;
                return node.textContent.trim().length > 0 ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_SKIP;
            }
        }, false);
        let target = null, maxLen = 0, node;
        while ((node = walker.nextNode())) {
            const trimmed = node.textContent.trim();
            if (trimmed.length > maxLen) {
                maxLen = trimmed.length;
                target = node;
            }
        }
        return target;
    }

    function buildStableSelector(el) {
        if (el.id) return '#' + el.id;
        const testId = el.getAttribute('data-testid') || el.getAttribute('data-test');
        if (testId) return `[data-testid="${testId}"]`;
        const ariaLabel = el.getAttribute('aria-label');
        if (ariaLabel) return `${el.tagName.toLowerCase()}[aria-label="${ariaLabel}"]`;
        const role = el.getAttribute('role');
        if (role) return `${el.tagName.toLowerCase()}[role="${role}"]`;

        // Semantic class
        if (el.className && typeof el.className === 'string') {
            const classes = el.className.trim().split(/\\s+/).filter(c => c.length > 2 && !c.startsWith('css-'));
            if (classes.length > 0) {
                // Check if class is unique on page
                if (document.querySelectorAll('.' + classes[0]).length === 1) {
                    return `.${classes[0]}`;
                }
                const compound = classes.slice(0, 2).join('.');
                if (document.querySelectorAll('.' + compound).length === 1) {
                    return `.${compound}`;
                }
            }
        }

        // Hierarchical scoped selector (parent + tag + nth-of-type)
        const parent = el.parentElement;
        if (parent) {
            let parentSel = parent.id ? '#' + parent.id :
                (parent.getAttribute('data-testid') ? `[data-testid="${parent.getAttribute('data-testid')}"]` : null);

            if (!parentSel && parent.className && typeof parent.className === 'string') {
                const pClasses = parent.className.trim().split(/\\s+/).filter(c => c.length > 2 && !c.startsWith('css-'));
                if (pClasses.length > 0) parentSel = `.${pClasses[0]}`;
            }

            if (!parentSel) parentSel = parent.tagName.toLowerCase();

            const siblings = Array.from(parent.children).filter(c => c.tagName === el.tagName);
            const index = siblings.indexOf(el) + 1;
            const tag = el.tagName.toLowerCase();
            return siblings.length > 1 ? `${parentSel} > ${tag}:nth-of-type(${index})` : `${parentSel} > ${tag}`;
        }

        return el.tagName.toLowerCase();
    }

    function resolveElementType(tag, role, classes) {
        const t = tag.toLowerCase();
        if (t === 'button' || role === 'button' || classes.includes('btn') || classes.includes('button')) return 'button';
        if (role === 'tab' || classes.includes('tab') || classes.includes('nav-item')) return 'nav_tab';
        if (t === 'a' || classes.includes('link')) return 'nav_tab';
        if (/^h[1-6]$/.test(t)) return 'header';
        if (classes.includes('badge') || classes.includes('tag') || classes.includes('pill')) return 'badge';
        return 'label';
    }

    const discovered = [];
    const seenTextNodes = new Set();
    const candidates = document.querySelectorAll(
        'button, a, [role="button"], [role="tab"], .btn, nav a, h1, h2, h3, h4, label, [class*="price"], [class*="tag"], [class*="badge"], [class*="item"], [data-testid*="button"], [data-testid*="menu"], [data-testid*="nav"], p, span[class]'
    );

    let assignedId = 0;
    candidates.forEach((el) => {
        if (el.closest('#polyglot-inspector-root')) return;

        const style = window.getComputedStyle(el);
        if (style.display === 'none' || style.visibility === 'hidden' || parseFloat(style.opacity) === 0) return;

        const rect = el.getBoundingClientRect();
        if (rect.width <= 4 || rect.height <= 4) return;

        const textNode = findTargetTextNode(el);
        if (!textNode) return;

        // Deduplication: Avoid selecting both parent and child for identical text
        if (seenTextNodes.has(textNode)) return;
        seenTextNodes.add(textNode);

        const rawText = textNode.textContent.trim();
        if (!rawText || rawText.length < 2 || rawText.length > 100) return;

        const padLeft = parseFloat(style.paddingLeft) || 0;
        const padRight = parseFloat(style.paddingRight) || 0;
        const elemWidth = el.clientWidth > 0 ? el.clientWidth : rect.width;
        const contentWidth = Math.max(0, elemWidth - padLeft - padRight);

        const parent = el.parentElement;
        const parentStyle = parent ? window.getComputedStyle(parent) : null;
        const parentRect = parent ? parent.getBoundingClientRect() : null;

        const classes = typeof el.className === 'string' ? el.className.split(' ') : [];
        const role = el.getAttribute('role') || '';
        const elemType = resolveElementType(el.tagName, role, classes);

        const isRigid = (style.width.endsWith('px') && parseFloat(style.width) < 100 && parseFloat(style.width) > 0) ||
                        (style.flexShrink === '0' && style.whiteSpace === 'nowrap');

        const polyglotId = String(assignedId++);
        el.setAttribute('data-polyglot-id', polyglotId);

        discovered.push({
            id: polyglotId,
            tag: el.tagName.toLowerCase(),
            text: rawText,
            elementType: elemType,
            selector: buildStableSelector(el),
            clientWidth: el.clientWidth,
            clientHeight: el.clientHeight,
            contentWidth: contentWidth,
            rectWidth: rect.width,
            rectHeight: rect.height,
            fontSize: parseFloat(style.fontSize) || 14.0,
            fontWeight: parseInt(style.fontWeight, 10) || 400,
            whiteSpace: style.whiteSpace,
            overflow: style.overflow,
            flexShrink: style.flexShrink,
            isRigidWidth: isRigid,
            parentTag: parent ? parent.tagName.toLowerCase() : '',
            parentDisplay: parentStyle ? parentStyle.display : '',
            parentFlexWrap: parentStyle ? parentStyle.flexWrap : '',
            parentWidth: parentRect ? parentRect.width : 0
        });
    });

    return discovered;
}
"""

class DOMScanner:
    @staticmethod
    def discover_elements(page) -> List[Dict[str, Any]]:
        return page.evaluate(JS_DISCOVER_ELEMENTS)
