// CSS custom properties of the QuantForge tokens (presentation/design-system/project/tokens.json),
// the same mapping as the design system's render check (tools/build_test.py): Paper by
// default, Graphite under [data-theme="dark"] or when the system prefers a dark scheme.
import tokens from '@design-system/tokens.json';

type Theme = 'light' | 'dark';
type Value = string | { light: string; dark?: string | null };

function value(token: Value, theme: Theme): string {
  const raw = typeof token === 'string' ? token : (token[theme] ?? token.light);
  return raw.startsWith('{') ? `var(--${raw.slice(1, -1)})` : raw;
}

function themed(theme: Theme): string {
  return [...tokens.color.tokens, ...tokens.shadow.tokens]
    .map((token) => `--${token.name}:${value(token.value as Value, theme)};`)
    .join('');
}

export function tokensCss(): string {
  const fixed = [...tokens.spacing.tokens, ...tokens.radius.tokens]
    .map((token) => `--${token.name}:${token.value};`)
    .concat(Object.entries(tokens.type.families).map(([family, stack]) => `--font-${family}:${stack};`))
    .join('');
  return [
    `:root,[data-theme="light"]{${themed('light')}}`,
    `[data-theme="dark"]{${themed('dark')}}`,
    `@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){${themed('dark')}}}`,
    `:root{${fixed}}`,
  ].join('\n');
}

export function installTokens(): void {
  const style = document.createElement('style');
  style.dataset.quantforgeTokens = '';
  style.textContent = tokensCss();
  document.head.prepend(style);
}
