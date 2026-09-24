import { useSyncExternalStore } from 'react';

export type Route = { screen: 'registry' } | { screen: 'hypothesis'; id: string };

/** Routes live in the URL hash, so the API needs no fallback route for the app. */
export function parseRoute(hash: string): Route {
  const match = /^#\/h\/([^/?#]+)$/.exec(hash);
  return match ? { screen: 'hypothesis', id: decodeURIComponent(match[1]) } : { screen: 'registry' };
}

export const href = {
  registry: '#/',
  hypothesis: (id: string) => `#/h/${encodeURIComponent(id)}`,
};

function subscribe(onChange: () => void) {
  window.addEventListener('hashchange', onChange);
  return () => window.removeEventListener('hashchange', onChange);
}

export function useRoute(): Route {
  return parseRoute(useSyncExternalStore(subscribe, () => window.location.hash));
}
