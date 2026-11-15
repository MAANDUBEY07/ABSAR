import test from "node:test";
import assert from "node:assert/strict";
import { resolveAccessToken, unauthorizedAuthAction } from "../src/services/auth-token.mjs";

const now = 1_800_000_000_000;
const validSession = {
  access_token: "supabase-session-token",
  expires_at: Math.floor(now / 1000) + 3600,
  user: { id: "student-1" },
};

test("uses a valid Supabase session when no local token exists", () => {
  assert.equal(resolveAccessToken("supabase", { supabaseSession: validSession }, now), validSession.access_token);
});

test("a stale local token cannot override the configured Supabase session", () => {
  assert.equal(resolveAccessToken("supabase", { localToken: "stale-local-token", supabaseSession: validSession }, now), validSession.access_token);
});

test("does not send an expired Supabase access token", () => {
  const expiredSession = { ...validSession, expires_at: Math.floor(now / 1000) - 1 };
  assert.equal(resolveAccessToken("supabase", { supabaseSession: expiredSession }, now), null);
  assert.equal(unauthorizedAuthAction("supabase", {
    currentSession: expiredSession,
    refreshError: new Error("Temporary network error"),
  }), "preserve-supabase");
});

test("returns no token when neither configured provider has credentials", () => {
  assert.equal(resolveAccessToken(null, { localToken: "stale-local-token", supabaseSession: validSession }, now), null);
  assert.equal(resolveAccessToken("supabase", { localToken: "stale-local-token" }, now), null);
});

test("a 401 with a still-valid Supabase session retries after refresh instead of signing out", () => {
  assert.equal(unauthorizedAuthAction("supabase", {
    refreshedSession: validSession,
    currentSession: validSession,
  }), "retry-supabase");
  assert.equal(unauthorizedAuthAction("supabase", {
    currentSession: validSession,
    refreshError: new Error("Temporary network error"),
  }), "preserve-supabase");
});

test("signs out when Supabase confirms the session or refresh token is invalid", () => {
  assert.equal(unauthorizedAuthAction("supabase", {}), "sign-out-supabase");
  assert.equal(unauthorizedAuthAction("supabase", {
    currentSession: validSession,
    refreshError: { status: 400, code: "invalid_grant", message: "Invalid grant" },
  }), "sign-out-supabase");
});

test("local authentication continues to use only the local token", () => {
  assert.equal(resolveAccessToken("local", { localToken: "local-token", supabaseSession: validSession }, now), "local-token");
  assert.equal(unauthorizedAuthAction("local", {}), "clear-local");
});
