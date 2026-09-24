import { describe, expect, it } from 'vitest';
import { href, parseRoute } from './route';

describe('routes', () => {
  it('reads the registry from an empty or unknown hash', () => {
    expect(parseRoute('')).toEqual({ screen: 'registry' });
    expect(parseRoute('#/')).toEqual({ screen: 'registry' });
    expect(parseRoute('#/somewhere/else')).toEqual({ screen: 'registry' });
  });

  it('reads a hypothesis id and round-trips encoded ids', () => {
    expect(parseRoute('#/h/demo_momentum')).toEqual({ screen: 'hypothesis', id: 'demo_momentum' });
    expect(parseRoute(href.hypothesis('a b/c'))).toEqual({ screen: 'hypothesis', id: 'a b/c' });
  });
});
