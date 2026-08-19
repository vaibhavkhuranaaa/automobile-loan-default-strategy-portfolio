import { useEffect, useState } from "react";

const BASE = import.meta.env.VITE_API_BASE_URL ?? (import.meta.env.DEV ? "http://127.0.0.1:8000" : "");

export async function get(path) {
  const response = await fetch(`${BASE}${path}`);
  if (!response.ok) {
    const detail = await response.json().catch(() => null);
    throw new Error(detail?.detail ?? `Request failed with ${response.status}`);
  }
  return response.json();
}

/** Fetch with the three states a view actually has to render: loading, error, data.
 *
 * Returns `stale` alongside `data` so a view that is refetching after a filter
 * change can keep the previous numbers on screen and dim them, rather than
 * collapsing to a skeleton and making the page jump on every keystroke.
 */
export function useApi(path, deps = []) {
  const [state, setState] = useState({ data: null, error: null, loading: true, stale: false });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let live = true;
    setState((previous) => ({ ...previous, loading: true, stale: previous.data != null }));
    get(path)
      .then((data) => live && setState({ data, error: null, loading: false, stale: false }))
      .catch((error) => live && setState({ data: null, error: error.message, loading: false, stale: false }));
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, attempt]);

  return { ...state, retry: () => setAttempt((value) => value + 1) };
}
