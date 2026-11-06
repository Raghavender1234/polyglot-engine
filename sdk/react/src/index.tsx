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

interface PolyglotContextType {
  config: PolyglotConfig;
  cache: Map<string, LocalizeResult>;
  localizeText: (
    sourceText: string,
    targetLocale: string,
    sourceLocale: string,
    maxWidthPx: number,
    fontSizePx?: number,
    fontWeight?: number,
    signal?: AbortSignal
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
      sourceLocale: string = defaultLocale,
      maxWidthPx: number,
      fontSizePx: number = 14,
      fontWeight: number = 400,
      signal?: AbortSignal
    ): Promise<LocalizeResult> => {
      const cacheKey = `${sourceText}|${sourceLocale}|${targetLocale}|${Math.round(maxWidthPx)}|${fontSizePx}|${fontWeight}`;
      if (cache.has(cacheKey)) {
        return cache.get(cacheKey)!;
      }

      const res = await fetch(`${apiUrl.replace(/\/$/, '')}/v1/localize`, {
        method: 'POST',
        signal,
        headers: {
          'Content-Type': 'application/json',
          ...(apiKey ? { 'X-API-Key': apiKey } : {})
        },
        body: JSON.stringify({
          source_text: sourceText,
          source_locale: sourceLocale,
          target_locales: [targetLocale],
          ui_context: {
            element_type: 'button',
            max_width_px: Math.max(maxWidthPx, 30),
            font_size_px: fontSizePx,
            font_weight: fontWeight
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
  } = {}
) {
  const context = useContext(PolyglotContext);
  const [result, setResult] = useState<LocalizeResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const containerRef = useRef<HTMLElement | null>(null);
  const [measuredWidth, setMeasuredWidth] = useState<number | null>(options.maxWidthPx || null);

  // ResizeObserver: monitors parent element width dynamically
  useEffect(() => {
    if (options.maxWidthPx) {
      setMeasuredWidth(options.maxWidthPx);
      return;
    }

    const node = containerRef.current;
    if (!node || typeof window === 'undefined' || !('ResizeObserver' in window)) {
      return;
    }

    const targetToObserve = node.parentElement || node;

    let debounceTimer: ReturnType<typeof setTimeout>;

    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
          const width = entry.contentRect.width;
          if (width > 0) {
            setMeasuredWidth(width);
          }
        }, 80);
      }
    });

    observer.observe(targetToObserve);

    return () => {
      clearTimeout(debounceTimer);
      observer.disconnect();
    };
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
        const srcLoc = options.sourceLocale || context.config.defaultLocale || 'en-US';

        const res = await context.localizeText(
          sourceText,
          targetLocale,
          srcLoc,
          effectiveWidth,
          options.fontSizePx || 14,
          options.fontWeight || 400,
          abortController.signal
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
  }, [context, sourceText, targetLocale, measuredWidth, options.sourceLocale, options.fontSizePx, options.fontWeight]);

  return { result, loading, error, containerRef, measuredWidth };
}

export interface SmartTextProps extends HTMLAttributes<HTMLSpanElement> {
  sourceText?: string;
  targetLocale: string;
  sourceLocale?: string;
  maxWidthPx?: number;
  fontSizePx?: number;
  fontWeight?: number;
  children?: ReactNode;
}

export function SmartText({
  sourceText,
  targetLocale,
  sourceLocale,
  maxWidthPx,
  fontSizePx = 14,
  fontWeight = 400,
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
    fontWeight
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
  children?: ReactNode;
}

export function SmartButton({
  sourceText,
  targetLocale,
  sourceLocale,
  maxWidthPx,
  fontSizePx = 14,
  fontWeight = 600,
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
    fontWeight
  });

  // Preserve child elements (e.g., icons) if children is non-string or compound
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
