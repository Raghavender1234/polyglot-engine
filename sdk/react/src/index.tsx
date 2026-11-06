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
    fits_container: bool;
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
    maxWidthPx: number,
    fontSizePx?: number,
    fontWeight?: number
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
      maxWidthPx: number,
      fontSizePx: number = 14,
      fontWeight: number = 400
    ): Promise<LocalizeResult> => {
      const cacheKey = `${sourceText}|${targetLocale}|${Math.round(maxWidthPx)}|${fontSizePx}|${fontWeight}`;
      if (cache.has(cacheKey)) {
        return cache.get(cacheKey)!;
      }

      const res = await fetch(`${apiUrl.replace(/\/$/, '')}/v1/localize`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(apiKey ? { 'X-API-Key': apiKey } : {})
        },
        body: JSON.stringify({
          source_text: sourceText,
          source_locale: defaultLocale,
          target_locales: [targetLocale],
          ui_context: {
            element_type: 'button',
            max_width_px: Math.max(maxWidthPx, 40),
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

  useEffect(() => {
    let isMounted = true;

    async function compute() {
      if (!context) return;
      setLoading(true);
      setError(null);

      try {
        let width = options.maxWidthPx;
        if (!width && containerRef.current) {
          const rect = containerRef.current.getBoundingClientRect();
          const computedStyle = window.getComputedStyle(containerRef.current);
          const paddingLeft = parseFloat(computedStyle.paddingLeft) || 0;
          const paddingRight = parseFloat(computedStyle.paddingRight) || 0;
          width = rect.width - paddingLeft - paddingRight;
        }

        const effectiveWidth = width && width > 0 ? width : 145;
        const res = await context.localizeText(
          sourceText,
          targetLocale,
          effectiveWidth,
          options.fontSizePx || 14,
          options.fontWeight || 400
        );

        if (isMounted) {
          setResult(res);
        }
      } catch (err) {
        if (isMounted) {
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
    };
  }, [context, sourceText, targetLocale, options.maxWidthPx, options.fontSizePx, options.fontWeight]);

  return { result, loading, error, containerRef };
}

export interface SmartTextProps extends HTMLAttributes<HTMLSpanElement> {
  sourceText: string;
  targetLocale: string;
  maxWidthPx?: number;
  fontSizePx?: number;
  fontWeight?: number;
}

export function SmartText({
  sourceText,
  targetLocale,
  maxWidthPx,
  fontSizePx = 14,
  fontWeight = 400,
  style,
  className,
  ...rest
}: SmartTextProps) {
  const { result, loading, containerRef } = usePolyglot(sourceText, targetLocale, {
    maxWidthPx,
    fontSizePx,
    fontWeight
  });

  const displayText = result ? result.ui_safe_text : sourceText;

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
  sourceText: string;
  targetLocale: string;
  maxWidthPx?: number;
  fontSizePx?: number;
  fontWeight?: number;
}

export function SmartButton({
  sourceText,
  targetLocale,
  maxWidthPx,
  fontSizePx = 14,
  fontWeight = 600,
  style,
  className,
  children,
  ...rest
}: SmartButtonProps) {
  const { result, loading, containerRef } = usePolyglot(sourceText, targetLocale, {
    maxWidthPx,
    fontSizePx,
    fontWeight
  });

  const displayText = result ? result.ui_safe_text : sourceText;

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
      {displayText}
    </button>
  );
}
