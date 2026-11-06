import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useRef,
  useCallback,
  ReactNode,
  CSSProperties,
  ButtonHTMLAttributes,
  HTMLAttributes
} from 'react';

export interface PolyglotConfig {
  apiUrl: string;
  apiKey?: string;
  defaultLocale?: string;
}

export interface CSSRules {
  dir: 'ltr' | 'rtl';
  classes: string;
  font_family: string;
  line_height: string;
  letter_spacing: string;
  recommended_min_height_px?: number;
}

export interface LocalizeResult {
  raw_text: string;
  ui_safe_text: string;
  variant_used: 'standard' | 'compact' | 'ultra_short';
  overflow_prevented?: {
    rejected_full_text: string;
    rejected_width_px: number;
  };
  metrics: {
    measured_width_px: number;
    max_width_px: number;
    fits_container: boolean;
    recommended_font_scale: number;
  };
  css_rules: CSSRules;
}

export interface LocalizeOptions {
  maxWidthPx: number;
  sourceLocale?: string;
  fontSizePx?: number;
  fontWeight?: number;
  paddingXPx?: number;
  elementType?: string;
  signal?: AbortSignal;
}

interface PolyglotContextType {
  config: PolyglotConfig;
  cache: Map<string, LocalizeResult>;
  localizeText: (
    sourceText: string,
    targetLocale: string,
    options: LocalizeOptions
  ) => Promise<LocalizeResult>;
}

const PolyglotContext = createContext<PolyglotContextType | null>(null);

export function PolyglotProvider({
  apiUrl = 'https://polyglot-engine.onrender.com',
  apiKey,
  defaultLocale = 'en-US',
  children
}: {
  apiUrl?: string;
  apiKey?: string;
  defaultLocale?: string;
  children: ReactNode;
}) {
  const [cache] = useState(() => new Map<string, LocalizeResult>());

  const localizeText = useCallback(
    async (
      sourceText: string,
      targetLocale: string,
      options: LocalizeOptions
    ): Promise<LocalizeResult> => {
      const srcLoc = options.sourceLocale || defaultLocale;
      const fontSize = options.fontSizePx || 14;
      const weight = options.fontWeight || 400;
      const paddingX = options.paddingXPx || 0;
      const elemType = options.elementType || 'button';

      const cacheKey = `${sourceText}|${srcLoc}|${targetLocale}|${Math.round(options.maxWidthPx)}|${fontSize}|${weight}|${paddingX}`;
      if (cache.has(cacheKey)) {
        return cache.get(cacheKey)!;
      }

      const res = await fetch(`${apiUrl.replace(/\/$/, '')}/v1/localize`, {
        method: 'POST',
        signal: options.signal,
        headers: {
          'Content-Type': 'application/json',
          ...(apiKey ? { 'X-API-Key': apiKey } : {})
        },
        body: JSON.stringify({
          source_text: sourceText,
          source_locale: srcLoc,
          target_locales: [targetLocale],
          ui_context: {
            element_type: elemType,
            max_width_px: Math.max(options.maxWidthPx, 30),
            font_size_px: fontSize,
            font_weight: weight,
            padding_x_px: paddingX
          }
        })
      });

      if (!res.ok) {
        throw new Error(`Polyglot request failed with status ${res.status}`);
      }

      const data = await res.json();
      const result: LocalizeResult = data.results[targetLocale];
      cache.set(cacheKey, result);
      return result;
    },
    [apiUrl, apiKey, defaultLocale, cache]
  );

  return (
    <PolyglotContext.Provider value={{ config: { apiUrl, apiKey, defaultLocale }, cache, localizeText }}>
      {children}
    </PolyglotContext.Provider>
  );
}

export function usePolyglot(
  sourceText: string,
  targetLocale: string,
  options: {
    sourceLocale?: string;
    maxWidthPx?: number;
    fontSizePx?: number;
    fontWeight?: number;
    paddingXPx?: number;
    elementType?: string;
  } = {}
) {
  const context = useContext(PolyglotContext);
  const [result, setResult] = useState<LocalizeResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const containerRef = useRef<HTMLElement | null>(null);
  const [measuredWidth, setMeasuredWidth] = useState<number | null>(options.maxWidthPx || null);
  const [measuredPaddingX, setMeasuredPaddingX] = useState<number>(options.paddingXPx || 0);

  // Accurate content box measurement
  useEffect(() => {
    if (options.maxWidthPx) {
      setMeasuredWidth(options.maxWidthPx);
      return;
    }

    const node = containerRef.current;
    if (!node || typeof window === 'undefined') {
      return;
    }

    function calculateBox() {
      if (!node) return;
      const computed = window.getComputedStyle(node);
      const padLeft = parseFloat(computed.paddingLeft) || 0;
      const padRight = parseFloat(computed.paddingRight) || 0;
      const borderLeft = parseFloat(computed.borderLeftWidth) || 0;
      const borderRight = parseFloat(computed.borderRightWidth) || 0;
      const totalPadding = padLeft + padRight + borderLeft + borderRight;
      setMeasuredPaddingX(totalPadding);

      // Check if element has its own explicit width / max-width
      const explicitWidth = parseFloat(computed.width);
      const explicitMaxWidth = parseFloat(computed.maxWidth);

      if (!isNaN(explicitMaxWidth) && explicitMaxWidth > 0) {
        setMeasuredWidth(explicitMaxWidth);
      } else if (!isNaN(explicitWidth) && explicitWidth > 0 && computed.display !== 'inline') {
        setMeasuredWidth(explicitWidth);
      } else if (node.parentElement) {
        // Fallback to parent available width
        const parentComputed = window.getComputedStyle(node.parentElement);
        const parentPad = (parseFloat(parentComputed.paddingLeft) || 0) + (parseFloat(parentComputed.paddingRight) || 0);
        const parentWidth = node.parentElement.clientWidth - parentPad;
        if (parentWidth > 0) {
          setMeasuredWidth(parentWidth);
        }
      }
    }

    calculateBox();

    if ('ResizeObserver' in window) {
      let debounceTimer: ReturnType<typeof setTimeout>;
      const observer = new ResizeObserver(() => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(calculateBox, 80);
      });

      observer.observe(node);
      if (node.parentElement) observer.observe(node.parentElement);

      return () => {
        clearTimeout(debounceTimer);
        observer.disconnect();
      };
    }
  }, [options.maxWidthPx]);

  useEffect(() => {
    let isMounted = true;
    const abortController = new AbortController();

    async function compute() {
      if (!context || !sourceText || !targetLocale) return;
      setLoading(true);
      setError(null);

      try {
        const effectiveWidth = measuredWidth && measuredWidth > 0 ? measuredWidth : 145;
        const res = await context.localizeText(
          sourceText,
          targetLocale,
          {
            maxWidthPx: effectiveWidth,
            sourceLocale: options.sourceLocale,
            fontSizePx: options.fontSizePx || 14,
            fontWeight: options.fontWeight || 400,
            paddingXPx: options.paddingXPx !== undefined ? options.paddingXPx : measuredPaddingX,
            elementType: options.elementType || 'button',
            signal: abortController.signal
          }
        );

        if (isMounted) {
          setResult(res);
        }
      } catch (err: any) {
        if (isMounted && err.name !== 'AbortError') {
          setError(err instanceof Error ? err : new Error(String(err)));
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    }

    compute();

    return () => {
      isMounted = false;
      abortController.abort();
    };
  }, [context, sourceText, targetLocale, measuredWidth, measuredPaddingX, options.sourceLocale, options.fontSizePx, options.fontWeight, options.paddingXPx, options.elementType]);

  return { result, loading, error, containerRef, measuredWidth };
}

export interface SmartTextProps extends HTMLAttributes<HTMLSpanElement> {
  sourceText?: string;
  targetLocale: string;
  sourceLocale?: string;
  maxWidthPx?: number;
  fontSizePx?: number;
  fontWeight?: number;
  paddingXPx?: number;
  children?: ReactNode;
}

export function SmartText({
  sourceText,
  targetLocale,
  sourceLocale,
  maxWidthPx,
  fontSizePx = 14,
  fontWeight = 400,
  paddingXPx,
  style,
  className,
  children,
  ...rest
}: SmartTextProps) {
  const resolvedText = sourceText || (typeof children === 'string' ? children : '');

  const { result, containerRef } = usePolyglot(resolvedText, targetLocale, {
    sourceLocale,
    maxWidthPx,
    fontSizePx,
    fontWeight,
    paddingXPx,
    elementType: 'text'
  });

  const displayText = result ? result.ui_safe_text : (sourceText || children);

  const dynamicStyle: CSSProperties = {
    ...style,
    direction: result?.css_rules.dir || 'ltr',
    lineHeight: result?.css_rules.line_height || undefined,
    letterSpacing: result?.css_rules.letter_spacing || undefined,
    fontFamily: result?.css_rules.font_family || undefined
  };

  return (
    <span
      ref={containerRef as any}
      style={dynamicStyle}
      className={`polyglot-smart-text ${result?.css_rules.classes || ''} ${className || ''}`}
      {...rest}
    >
      {displayText}
    </span>
  );
}

export interface SmartButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  sourceText?: string;
  targetLocale: string;
  sourceLocale?: string;
  maxWidthPx?: number;
  fontSizePx?: number;
  fontWeight?: number;
  paddingXPx?: number;
  children?: ReactNode;
}

export function SmartButton({
  sourceText,
  targetLocale,
  sourceLocale,
  maxWidthPx,
  fontSizePx = 14,
  fontWeight = 600,
  paddingXPx,
  style,
  className,
  children,
  ...rest
}: SmartButtonProps) {
  const resolvedText = sourceText || (typeof children === 'string' ? children : '');

  const { result, containerRef } = usePolyglot(resolvedText, targetLocale, {
    sourceLocale,
    maxWidthPx,
    fontSizePx,
    fontWeight,
    paddingXPx,
    elementType: 'button'
  });

  let contentToRender: ReactNode = resolvedText;
  if (result) {
    if (typeof children === 'string' || !children) {
      contentToRender = result.ui_safe_text;
    } else {
      contentToRender = (
        <>
          {result.ui_safe_text}
          {React.Children.map(children, (child) => (typeof child === 'string' ? null : child))}
        </>
      );
    }
  } else {
    contentToRender = children || sourceText;
  }

  const dynamicStyle: CSSProperties = {
    ...style,
    direction: result?.css_rules.dir || 'ltr',
    lineHeight: result?.css_rules.line_height || undefined,
    letterSpacing: result?.css_rules.letter_spacing || undefined,
    fontFamily: result?.css_rules.font_family || undefined
  };

  return (
    <button
      ref={containerRef as any}
      style={dynamicStyle}
      className={`polyglot-smart-button ${result?.css_rules.classes || ''} ${className || ''}`}
      title={result?.overflow_prevented ? `Original: ${result.overflow_prevented.rejected_full_text}` : undefined}
      {...rest}
    >
      {contentToRender}
    </button>
  );
}
