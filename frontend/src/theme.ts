export type ThemePref = "light" | "dark" | "system";

const STORAGE_KEY = "airfare-idex-theme";

export function getStoredTheme(): ThemePref {
  try {
    const v = localStorage.getItem(STORAGE_KEY);
    if (v === "light" || v === "dark" || v === "system") return v;
  } catch {
    // localStorage can throw in some private-browsing contexts - fall through to the default
  }
  return "system";
}

export function applyTheme(theme: ThemePref): void {
  if (theme === "system") {
    document.documentElement.removeAttribute("data-theme");
  } else {
    document.documentElement.setAttribute("data-theme", theme);
  }
  try {
    localStorage.setItem(STORAGE_KEY, theme);
  } catch {
    // per-viewer convenience only - fine if it doesn't persist
  }
}
