import { describe, expect, it } from 'vitest';
import { tokensCss } from './tokens';

describe('design tokens', () => {
  const css = tokensCss();

  it('defines the Paper theme on :root and the Graphite theme for dark schemes', () => {
    expect(css).toContain(':root,[data-theme="light"]{--ground:#f4f3ef;');
    expect(css).toContain('[data-theme="dark"]{--ground:#0d0f11;');
    expect(css).toContain('@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--ground:#0d0f11;');
  });

  it('resolves token references and carries spacing, radii and fonts', () => {
    expect(css).toContain('--status-proposed:var(--ink-muted);');
    expect(css).toContain('--space-1:4px;');
    expect(css).toContain('--radius-xs:2px;');
    expect(css).toMatch(/--font-mono:"IBM Plex Mono"/);
  });
});
