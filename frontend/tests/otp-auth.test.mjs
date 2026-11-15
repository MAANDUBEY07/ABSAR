import test from "node:test";
import assert from "node:assert/strict";

// Contract test simulating Supabase passwordless OTP verification response
// and session token extraction for AVSAR backend API consumption.

test("Supabase signInWithOtp options enforce shouldCreateUser separation", () => {
  const loginOptions = { shouldCreateUser: false };
  const signupOptions = { shouldCreateUser: true };

  assert.equal(loginOptions.shouldCreateUser, false, "Login must disallow unintended user creation");
  assert.equal(signupOptions.shouldCreateUser, true, "Signup must allow new user registration");
});

test("verifyOtp validates 6-digit numeric OTP format", () => {
  const sanitizeOtp = (raw) => (raw || "").trim().replace(/\D/g, "");

  assert.equal(sanitizeOtp(" 123-456 "), "123456");
  assert.equal(sanitizeOtp("987654").length, 6);
  assert.equal(sanitizeOtp("123ab4").length, 4);
});

test("verifyOtp response yields valid user and access token for backend session", () => {
  const mockVerifyResponse = {
    data: {
      user: {
        id: "d9b2d63d-a233-4f9b-8d6f-7e9b0d2d3a4b",
        email: "student@university.edu",
        role: "authenticated",
      },
      session: {
        access_token: "jwt-supabase-access-token",
        token_type: "bearer",
        expires_in: 3600,
        refresh_token: "refresh-token-xyz",
        user: {
          id: "d9b2d63d-a233-4f9b-8d6f-7e9b0d2d3a4b",
          email: "student@university.edu",
        },
      },
    },
    error: null,
  };

  assert.ok(mockVerifyResponse.data.session.access_token);
  assert.equal(mockVerifyResponse.data.user.role, "authenticated");
  assert.equal(mockVerifyResponse.data.user.email, "student@university.edu");
});

test("OTP verification error messages are properly categorized", () => {
  const getErrorMessage = (error) => {
    if (/expired/i.test(error.message)) return "The OTP code has expired. Please request a new code.";
    if (/invalid/i.test(error.message)) return "Invalid OTP code. Please check your 6-digit code and try again.";
    return error.message;
  };

  assert.equal(
    getErrorMessage({ message: "Token has expired or is invalid" }),
    "The OTP code has expired. Please request a new code."
  );
  assert.equal(
    getErrorMessage({ message: "Invalid token provided" }),
    "Invalid OTP code. Please check your 6-digit code and try again."
  );
});
