import { useEffect, useState } from 'react';
import { ApiError } from './api';

export type Resource<T> =
  | { state: 'loading' }
  | { state: 'ready'; data: T }
  | { state: 'failed'; error: ApiError };

/** Loads once per change of `key`; a late response for an older key is dropped. */
export function useResource<T>(key: string, load: () => Promise<T>): Resource<T> {
  const [resource, setResource] = useState<{ key: string; value: Resource<T> }>({
    key,
    value: { state: 'loading' },
  });
  useEffect(() => {
    let current = true;
    setResource({ key, value: { state: 'loading' } });
    load().then(
      (data) => current && setResource({ key, value: { state: 'ready', data } }),
      (error: unknown) =>
        current &&
        setResource({
          key,
          value: {
            state: 'failed',
            error: error instanceof ApiError ? error : new ApiError(0, String(error), null),
          },
        }),
    );
    return () => {
      current = false;
    };
    // `load` is recreated on every render; `key` names what it loads.
  }, [key]);
  return resource.key === key ? resource.value : { state: 'loading' };
}
