# @polyglot-engine/react

> Runtime UI Layout Protection & Localization SDK for React, Next.js, and React Native.

Traditional translation libraries leave UI layouts vulnerable to breaking when strings expand. `@polyglot-engine/react` automatically measures the component's rendered pixel container, queries the Polyglot Engine, selects the meaning-preserving variant that fits, and applies script-safe typography rules (BiDi isolates, Urdu line-heights, and zero-letter-spacing cursives).

---

## 📦 Installation

```bash
npm install @polyglot-engine/react
# or
pnpm add @polyglot-engine/react
# or
yarn add @polyglot-engine/react
```

---

## ⚡ Quickstart

### 1. Wrap your application with `PolyglotProvider`

```tsx
// app/layout.tsx or App.tsx
import { PolyglotProvider } from '@polyglot-engine/react';

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <PolyglotProvider 
      apiUrl="https://polyglot-engine.onrender.com"
      apiKey={process.env.NEXT_PUBLIC_POLYGLOT_API_KEY}
    >
      {children}
    </PolyglotProvider>
  );
}
```

---

### 2. Use `<SmartButton>`

The `<SmartButton>` automatically measures its own container. If German or Urdu expands too wide, it automatically renders the compact variant without breaking:

```tsx
import { SmartButton } from '@polyglot-engine/react';

export function CheckoutCTA({ userLocale }: { userLocale: string }) {
  return (
    <SmartButton
      sourceText="Complete Purchase - $49.99"
      targetLocale={userLocale}
      className="w-36 py-2.5 bg-blue-600 hover:bg-blue-500 text-white rounded-lg font-semibold"
    />
  );
}
```

---

### 3. Use `<SmartText>` in Cards or Navigation Tabs

```tsx
import { SmartText } from '@polyglot-engine/react';

export function NavItem({ locale }: { locale: string }) {
  return (
    <div className="w-28 truncate border-b">
      <SmartText 
        sourceText="Account Settings" 
        targetLocale={locale} 
        fontSizePx={13} 
      />
    </div>
  );
}
```

---

### 4. Direct Hook: `usePolyglot`

```tsx
import { usePolyglot } from '@polyglot-engine/react';

function CustomComponent({ locale }: { locale: string }) {
  const { result, loading, error, containerRef } = usePolyglot(
    "Subscribe to Pro (Annual)",
    locale,
    { maxWidthPx: 140, fontSizePx: 14 }
  );

  return (
    <div ref={containerRef}>
      {loading ? "Loading..." : result?.ui_safe_text}
      {result?.overflow_prevented && (
        <span className="text-xs text-amber-500">
          Saved {result.overflow_prevented.rejected_width_px}px!
        </span>
      )}
    </div>
  );
}
```
