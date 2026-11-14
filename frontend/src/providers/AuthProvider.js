"use client";

import { createContext, useCallback, useEffect, useMemo, useState } from "react";
import { api, localAuth } from "@/services/api";
import { getAuthProvider, getStoredLocalToken, setAuthProvider, storeLocalToken, unauthorizedAuthAction } from "@/services/auth-token.mjs";
import { configureSupabase, getSupabaseClient } from "@/services/supabase";

export const AuthContext = createContext(null);

function authError(error) {
  return error?.message || "Authentication failed. Please try again.";
}

export function AuthProvider({ children }) {
  const [provider, setProvider] = useState(null);
  const [authConfig, setAuthConfig] = useState(null);
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadCurrentUser = useCallback(async (fallbackUser = null, authProvider = getAuthProvider(), mayRefresh = true) => {
    try {
      const current = await api.currentUser();
      setError("");
      setUser({ ...(fallbackUser || {}), ...current });
      return current;
    } catch (requestError) {
      if (requestError.status === 401) {
        if (authProvider === "local") {
          storeLocalToken(null);
          setUser(null);
          setError("Your local session expired. Please sign in again.");
          return null;
        }

        if (authProvider === "supabase" && mayRefresh) {
          const client = getSupabaseClient();
          if (!client) {
            setUser(null);
            setError("Your authentication session is unavailable. Please sign in again.");
            return null;
          }

          let refreshError = null;
          let refreshedSession = null;
          try {
            const refreshed = await client.auth.refreshSession();
            refreshError = refreshed.error;
            refreshedSession = refreshed.data?.session || null;
          } catch (error) {
            refreshError = error;
          }

          if (refreshedSession?.access_token) {
            setUser(refreshedSession.user || fallbackUser);
            return loadCurrentUser(refreshedSession.user || fallbackUser, authProvider, false);
          }

          let currentSession = null;
          try {
            const current = await client.auth.getSession();
            currentSession = current.data?.session || null;
            if (!refreshError) refreshError = current.error;
          } catch (error) {
            if (!refreshError) refreshError = error;
          }

          const action = unauthorizedAuthAction(authProvider, { refreshedSession, currentSession, refreshError });
          if (action === "sign-out-supabase") {
            try { await client.auth.signOut(); }
            finally {
              setUser(null);
              setError("Your authentication session is no longer valid. Please sign in again.");
            }
            return null;
          }

          // A failed request or transient refresh error is not proof the provider session is invalid.
          setUser(currentSession?.user || fallbackUser);
          setError(requestError.message);
          return null;
        }

        // A second 401 after a successful provider refresh must not clear that provider session.
        setUser(fallbackUser);
        setError(requestError.message);
      } else {
        setError(requestError.message);
        setUser(fallbackUser);
      }
      return null;
    }
  }, []);

  useEffect(() => {
    let active = true;
    let subscription;
    async function initialize() {
      try {
        const config = await api.authConfig();
        if (!active) return;
        setAuthProvider(config.provider);
        setAuthConfig(config);
        setProvider(config.provider);
        if (config.provider === "supabase") {
          const client = configureSupabase({ url: config.supabase_url, anonKey: config.supabase_anon_key });
          if (!client) throw new Error("Supabase is selected by the backend. Set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY.");
          const { data, error: sessionError } = await client.auth.getSession();
          if (sessionError) throw sessionError;
          if (active && data.session) {
            setUser(data.session.user);
            await loadCurrentUser(data.session.user, config.provider);
          }
          const listener = client.auth.onAuthStateChange((_event, session) => {
            if (!active) return;
            setUser(session?.user || null);
            if (session) queueMicrotask(() => loadCurrentUser(session.user, "supabase"));
          });
          subscription = listener.data.subscription;
        } else if (config.provider === "local") {
          if (getStoredLocalToken()) await loadCurrentUser(null, config.provider);
        } else {
          throw new Error(`The backend auth provider “${config.provider}” is not supported by this frontend.`);
        }
      } catch (initializationError) {
        if (active) {
          setError(authError(initializationError));
          if (!process.env.NEXT_PUBLIC_SUPABASE_URL || !process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY) {
            setUser(null);
          }
        }
      } finally {
        if (active) setLoading(false);
      }
    }
    initialize();
    return () => {
      active = false;
      subscription?.unsubscribe();
    };
  }, [loadCurrentUser]);

  const signIn = useCallback(async ({ email, password }) => {
    setError("");
    if (provider === "local") {
      const result = await localAuth("login", { email, password });
      if (!result?.access_token) throw new Error("The local auth service did not return an access token.");
      storeLocalToken(result.access_token);
      await loadCurrentUser({ email }, "local");
      return;
    }
    const client = getSupabaseClient();
    if (!client) throw new Error("Supabase authentication is not configured.");
    const { data, error: signInError } = await client.auth.signInWithPassword({ email, password });
    if (signInError) throw signInError;
    if (!data.session) throw new Error("Sign in completed without a session. Check your email verification settings.");
    setUser(data.user);
    await loadCurrentUser(data.user, "supabase");
  }, [loadCurrentUser, provider]);

  const signUp = useCallback(async ({ email, password }) => {
    setError("");
    if (provider === "local") {
      const result = await localAuth("signup", { email, password });
      if (!result?.access_token) throw new Error("The local auth service did not return an access token.");
      storeLocalToken(result.access_token);
      await loadCurrentUser({ email }, "local");
      return { confirmationRequired: false };
    }
    const client = getSupabaseClient();
    if (!client) throw new Error("Supabase authentication is not configured.");
    const { data, error: signUpError } = await client.auth.signUp({ email, password });
    if (signUpError) throw signUpError;
    if (data.session) {
      setUser(data.user);
      await loadCurrentUser(data.user, "supabase");
    }
    return { confirmationRequired: !data.session };
  }, [loadCurrentUser, provider]);

  const signOut = useCallback(async () => {
    setError("");
    try { if (user) await api.logout(); }
    catch (logoutError) { setError(logoutError.message); }
    if (provider === "local") storeLocalToken(null);
    else await getSupabaseClient()?.auth.signOut();
    setUser(null);
  }, [provider, user]);

  const value = useMemo(() => ({
    provider, authConfig, user, loading, error, setError, signIn, signUp, signOut,
    refreshUser: () => loadCurrentUser(user, provider),
  }), [provider, authConfig, user, loading, error, signIn, signUp, signOut, loadCurrentUser]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
