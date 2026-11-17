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

  const sendOtp = useCallback(async ({ email, isSignUp = false }) => {
    setError("");
    const normalizedEmail = (email || "").trim().toLowerCase();
    if (!normalizedEmail) throw new Error("Please enter a valid email address.");

    if (provider === "local") {
      // Local dev emulation: directly proceed to OTP verification phase
      return { success: true, email: normalizedEmail, simulated: true };
    }

    const client = getSupabaseClient();
    if (!client) throw new Error("Supabase authentication is not configured.");

    const { error: otpError } = await client.auth.signInWithOtp({
      email: normalizedEmail,
      options: {
        shouldCreateUser: Boolean(isSignUp),
      },
    });

    if (otpError) {
      // Handle Supabase error codes for existing or missing users gracefully
      const msg = otpError.message || "";
      if (!isSignUp && (otpError.status === 400 || /user not found|not registered|sign up/i.test(msg))) {
        throw new Error("No account found with this email. Please create an account first.");
      }
      throw otpError;
    }

    return { success: true, email: normalizedEmail };
  }, [provider]);

  const verifyOtp = useCallback(async ({ email, token }) => {
    setError("");
    const normalizedEmail = (email || "").trim().toLowerCase();
    const cleanToken = (token || "").trim().replace(/\D/g, "");

    if (!normalizedEmail) throw new Error("Email is required.");
    if (cleanToken.length !== 6) throw new Error("Please enter the complete 6-digit OTP code.");

    if (provider === "local") {
      // Support local development login/signup emulation with OTP
      const emulatedPassword = cleanToken.length < 12 ? `${cleanToken}_local_dev_pass` : cleanToken;
      const result = await localAuth("login", { email: normalizedEmail, password: emulatedPassword }).catch(async () => {
        return await localAuth("signup", { email: normalizedEmail, password: emulatedPassword });
      });
      if (!result?.access_token) throw new Error("Local authentication failed.");
      storeLocalToken(result.access_token);
      await loadCurrentUser({ email: normalizedEmail }, "local");
      return;
    }

    const client = getSupabaseClient();
    if (!client) throw new Error("Supabase authentication is not configured.");

    const { data, error: verifyError } = await client.auth.verifyOtp({
      email: normalizedEmail,
      token: cleanToken,
      type: "email",
    });

    if (verifyError) {
      if (/expired/i.test(verifyError.message)) {
        throw new Error("The OTP code has expired. Please request a new code.");
      }
      if (/invalid/i.test(verifyError.message)) {
        throw new Error("Invalid OTP code. Please check your 6-digit code and try again.");
      }
      throw verifyError;
    }

    if (!data.session) {
      throw new Error("Verification completed without an active session. Please try again.");
    }

    setUser(data.user);
    await loadCurrentUser(data.user, "supabase");
  }, [loadCurrentUser, provider]);

  // Backward-compatibility wrappers for any legacy caller
  const signIn = useCallback(async ({ email, password }) => {
    return sendOtp({ email, isSignUp: false });
  }, [sendOtp]);

  const signUp = useCallback(async ({ email, password }) => {
    return sendOtp({ email, isSignUp: true });
  }, [sendOtp]);

  const signOut = useCallback(async () => {
    setError("");
    try { if (user) await api.logout(); }
    catch (logoutError) { setError(logoutError.message); }
    if (provider === "local") storeLocalToken(null);
    else await getSupabaseClient()?.auth.signOut();
    setUser(null);
    if (typeof window !== "undefined") {
      try {
        localStorage.removeItem("avsar_auth_tokens");
        localStorage.removeItem("avsar_profile_cache");
        sessionStorage.clear();
      } catch {}
    }
  }, [provider, user]);

  const value = useMemo(() => ({
    provider, authConfig, user, loading, error, setError,
    sendOtp, verifyOtp, signIn, signUp, signOut,
    refreshUser: () => loadCurrentUser(user, provider),
  }), [provider, authConfig, user, loading, error, sendOtp, verifyOtp, signIn, signUp, signOut, loadCurrentUser]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
