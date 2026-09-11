// Syncs a small slice of app state to a URL query parameter, so the
// current view (tab, selected route, tracked date, selected festival) can
// be bookmarked, refreshed, or shared as a direct link instead of being
// lost. Deliberately plain History API + URLSearchParams rather than a
// routing library: every synced value lives on the SAME path ("/"), only
// the query string changes, so no server-side route config is needed and
// no new dependency is introduced for what's ultimately a handful of
// query params.
//
// Writes always use replaceState, not pushState: the goal here is "the
// URL always reflects what's on screen" (for bookmarking/sharing/refresh),
// not "every click is a back-button stop" - pushing on every filter
// tweak would make the browser back button feel broken instead of useful.

import { useCallback, useEffect, useState } from "react";

type Listener = () => void;
const listeners = new Set<Listener>();

function notifyAll() {
  listeners.forEach((l) => l());
}

if (typeof window !== "undefined") {
  window.addEventListener("popstate", notifyAll);
}

function readParam(key: string): string | null {
  if (typeof window === "undefined") return null;
  return new URLSearchParams(window.location.search).get(key);
}

function writeParam(key: string, value: string | null) {
  if (typeof window === "undefined") return;
  const params = new URLSearchParams(window.location.search);
  if (value == null || value === "") {
    params.delete(key);
  } else {
    params.set(key, value);
  }
  const query = params.toString();
  const url = `${window.location.pathname}${query ? `?${query}` : ""}${window.location.hash}`;
  window.history.replaceState(window.history.state, "", url);
}

/**
 * A useState-shaped hook whose value is mirrored to `?key=value` in the
 * URL. `defaultValue` is used when the param is absent (and the param is
 * removed from the URL entirely if the value is later set back to it),
 * so a "default" view keeps a clean URL rather than always carrying every
 * param.
 */
export function useUrlState(
  key: string,
  defaultValue: string | null,
): [string | null, (value: string | null) => void] {
  const [value, setValue] = useState<string | null>(() => readParam(key) ?? defaultValue);

  useEffect(() => {
    const listener = () => setValue(readParam(key) ?? defaultValue);
    listeners.add(listener);
    return () => {
      listeners.delete(listener);
    };
  }, [key, defaultValue]);

  const set = useCallback(
    (next: string | null) => {
      writeParam(key, next === defaultValue ? null : next);
      setValue(next ?? defaultValue);
    },
    [key, defaultValue],
  );

  return [value, set];
}
