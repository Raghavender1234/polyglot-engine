"""
Polyglot Scanner — DOM Element Discovery & Geometry Inspection
Extracts interactive and text elements across the entire DOM tree (not restricted to a hardcoded tag list)
while deduplicating nested targets, filtering non-text/hidden nodes, and resolving robust selectors.
"""

from typing import Dict, Any, List, Tuple

JS_DISCOVER_ELEMENTS = """
() => {
    function findTargetTextNode(element) {
        // 1. Explicit text marker
        const explicitTextEl = element.querySelector('[data-polyglot-text]') || (element.hasAttribute('data-polyglot-text') ? element : null);
        if (explicitTextEl) {
            const walker = document.createTreeWalker(explicitTextEl, NodeFilter.SHOW_TEXT, null, false);
            let n;
            while ((n = walker.nextNode())) {
                if (n.textContent.trim().length > 0) return n;
            }
        }

        // 2. Direct child text node
        for (let i = 0; i < element.childNodes.length; i++) {
            const child = element.childNodes[i];
            if (child.nodeType === Node.TEXT_NODE && child.textContent.trim().length > 0) return child;
        }

        // 3. For interactive or leaf elements, walk down into inline wrappers (e.g. <button><span>Text</span></button>)
        // Structural containers (div, nav, section, ul, header, etc.) should NEVER steal text from child elements!
        const tag = element.tagName.toLowerCase();
        const isInteractiveOrLeaf = /^(button|a|summary|label|p|span|h[1-6])$/.test(tag) ||
            element.getAttribute('role') === 'button' ||
            element.getAttribute('role') === 'tab' ||
            element.getAttribute('role') === 'menuitem';

        if (!isInteractiveOrLeaf) {
            return null;
        }

        const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT, {
            acceptNode(node) {
                const parent = node.parentElement;
                if (!parent) return NodeFilter.FILTER_REJECT;
                const ptag = parent.tagName.toLowerCase();
                if (ptag === 'svg' || ptag === 'path' || ptag === 'i' || ptag === 'script' || ptag === 'style') return NodeFilter.FILTER_REJECT;
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
    const allDomElements = document.body ? document.body.querySelectorAll('*') : [];
    let excludedCount = 0;

    const NON_TEXT_TAGS = new Set([
        'script', 'style', 'svg', 'path', 'noscript', 'template', 'iframe', 'canvas',
        'video', 'audio', 'br', 'hr', 'meta', 'link', 'source', 'track'
    ]);

    let assignedId = 0;
    allDomElements.forEach((el) => {
        if (el.closest('#polyglot-inspector-root')) return;

        const tagName = el.tagName.toLowerCase();
        if (NON_TEXT_TAGS.has(tagName)) {
            excludedCount++;
            return;
        }

        const style = window.getComputedStyle(el);
        if (style.display === 'none' || style.visibility === 'hidden' || parseFloat(style.opacity) === 0) {
            excludedCount++;
            return;
        }

        const rect = el.getBoundingClientRect();
        if (rect.width <= 4 || rect.height <= 4) {
            excludedCount++;
            return;
        }

        const textNode = findTargetTextNode(el);
        if (!textNode) {
            return;
        }

        // Deduplication: Avoid selecting both parent and child for identical text
        if (seenTextNodes.has(textNode)) return;
        seenTextNodes.add(textNode);

        const rawText = textNode.textContent.trim();
        if (!rawText || rawText.length < 2 || rawText.length > 120) return;

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
            tag: tagName,
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
            direction: style.direction,
            unicodeBidi: style.unicodeBidi,
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

    return {
        discovered: discovered,
        totalDomElements: allDomElements.length,
        excludedCount: excludedCount
    };
}
"""

class DOMScanner:
    @staticmethod
    def discover_elements(page) -> List[Dict[str, Any]]:
        res = page.evaluate(JS_DISCOVER_ELEMENTS)
        if isinstance(res, dict) and "discovered" in res:
            return res["discovered"]
        return res

    @staticmethod
    def discover_with_stats(page) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        res = page.evaluate(JS_DISCOVER_ELEMENTS)
        if isinstance(res, dict) and "discovered" in res:
            return res["discovered"], {
                "totalDomElements": res.get("totalDomElements", 0),
                "excludedByDesign": res.get("excludedCount", 0),
                "discoveredCount": len(res.get("discovered", []))
            }
        return res, {
            "totalDomElements": len(res),
            "excludedByDesign": 0,
            "discoveredCount": len(res)
        }
