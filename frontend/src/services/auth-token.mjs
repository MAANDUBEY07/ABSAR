const LOCAL_TOKEN_KEY = "avsar.local.access-token";

let configuredProvider = null;

export function setAuthProvider(provider) {
  configuredProvider = provider === "local" || provider === "supabase" ? provider : null;
}

export function getAuthProvider() {
  return configuredProvider;
}

export function resolveAccessToken(provider, { localToken = null, supabaseSession = null } = {}, nowMs = Date.now()) {
  if (provider === "local") return localToken || null;
  if (provider !== "supabase") return null;

  const token = supabaseSession?.access_token;
  if (!token) return null;
  if (Number.isFinite(supabaseSession.expires_at) && supabaseSession.expires_at <= Math.floor(nowMs / 1000)) {
    return null;
  }
  return token;
}

function isTerminalRefreshError(error) {
  const code = String(error?.code || "").toLowerCase();
  if (["invalid_grant", "refresh_token_not_found", "refresh_token_already_used"].includes(code)) return true;
  return error?.status === 400 && /invalid refresh token|refresh token.*not found|invalid grant/i.test(error?.message || "");
}

export function unauthorizedAuthAction(provider, { refreshedSession = null, currentSession = null, refreshError = null } = {}) {
  if (provider === "local") return "clear-local";
  if (provider !== "supabase") return "preserve";
  if (refreshedSession?.access_token) return "retry-supabase";
  if (!currentSession || isTerminalRefreshError(refreshError)) return "sign-out-supabase";
  return "preserve-supabase";
}

export function getStoredLocalToken() {
  if (typeof window === "undefined") return null;
  try { return window.sessionStorage.getItem(LOCAL_TOKEN_KEY); }
  catch { return null; }
}

export function storeLocalToken(token) {
  if (typeof window === "undefined") return;
  try {
    if (token) window.sessionStorage.setItem(LOCAL_TOKEN_KEY, token);
    else window.sessionStorage.removeItem(LOCAL_TOKEN_KEY);
  } catch { /* Storage can be disabled by browser policy. */ }
}
