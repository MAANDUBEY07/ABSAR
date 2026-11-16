"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft, ArrowRight, CheckCircle2, KeyRound, Mail, RefreshCw } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import ThemeToggle from "@/components/ThemeToggle";
import BrandLogo from "@/components/BrandLogo";
import { returnToFromSearch } from "@/utils/returnTo.mjs";

const RESEND_COOLDOWN_SEC = 60;

export default function LoginPage() {
  const { user, loading, error: configError, sendOtp, verifyOtp } = useAuth();
  const router = useRouter();

  // Flow states: "email" -> "otp" -> "success"
  const [step, setStep] = useState("email");
  const [email, setEmail] = useState("");
  const [otp, setOtp] = useState(["", "", "", "", "", ""]);
  const [error, setError] = useState("");
  const [successMsg, setSuccessMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const [cooldown, setCooldown] = useState(0);
  const [returnTo, setReturnTo] = useState("/dashboard");

  const otpInputRefs = useRef([]);

  useEffect(() => {
    const destination = returnToFromSearch(window.location.search);
    setReturnTo(destination);
    if (!loading && user) router.replace(destination);
  }, [loading, user, router]);

  // Handle countdown timer for resend cooldown
  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = setInterval(() => {
      setCooldown((prev) => (prev > 0 ? prev - 1 : 0));
    }, 1000);
    return () => clearInterval(timer);
  }, [cooldown]);

  // Step 1: Send OTP to email for login (shouldCreateUser = false)
  async function handleSendOtp(event) {
    if (event) event.preventDefault();
    setError("");
    setSuccessMsg("");
    setBusy(true);

    try {
      await sendOtp({ email, isSignUp: false });
      setStep("otp");
      setCooldown(RESEND_COOLDOWN_SEC);
      setSuccessMsg(`A 6-digit code has been sent to ${email}`);
      // Focus first OTP field
      setTimeout(() => otpInputRefs.current[0]?.focus(), 100);
    } catch (requestError) {
      setError(requestError.message || "Unable to send login code. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  // Resend OTP
  async function handleResendOtp() {
    if (cooldown > 0 || busy) return;
    setError("");
    setSuccessMsg("");
    setBusy(true);

    try {
      await sendOtp({ email, isSignUp: false });
      setCooldown(RESEND_COOLDOWN_SEC);
      setSuccessMsg(`A fresh 6-digit code has been sent to ${email}`);
      setOtp(["", "", "", "", "", ""]);
      setTimeout(() => otpInputRefs.current[0]?.focus(), 100);
    } catch (requestError) {
      setError(requestError.message || "Failed to resend code. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  // Handle OTP digit changes
  function handleOtpChange(index, value) {
    const cleaned = value.replace(/\D/g, "");
    if (!cleaned) {
      const updated = [...otp];
      updated[index] = "";
      setOtp(updated);
      return;
    }

    // Support copy-paste of complete code
    if (cleaned.length > 1) {
      const pasteDigits = cleaned.slice(0, 6).split("");
      const updated = [...otp];
      pasteDigits.forEach((digit, i) => {
        if (index + i < 6) updated[index + i] = digit;
      });
      setOtp(updated);
      const nextFocus = Math.min(index + pasteDigits.length, 5);
      otpInputRefs.current[nextFocus]?.focus();
      return;
    }

    const updated = [...otp];
    updated[index] = cleaned;
    setOtp(updated);

    if (index < 5 && cleaned) {
      otpInputRefs.current[index + 1]?.focus();
    }
  }

  function handleOtpKeyDown(index, event) {
    if (event.key === "Backspace" && !otp[index] && index > 0) {
      otpInputRefs.current[index - 1]?.focus();
    }
  }

  // Step 2: Verify OTP
  async function handleVerifyOtp(event) {
    if (event) event.preventDefault();
    const token = otp.join("").trim();
    if (token.length !== 6) {
      setError("Please enter the complete 6-digit verification code.");
      return;
    }

    setError("");
    setBusy(true);

    try {
      await verifyOtp({ email, token });
      setStep("success");
      setTimeout(() => {
        router.replace(returnTo);
      }, 800);
    } catch (requestError) {
      setError(requestError.message || "Verification code is invalid or has expired.");
      setBusy(false);
    }
  }

  return (
    <main className="auth-shell auth-page">
      <header className="auth-topbar">
        <Link href="/" className="back-link">
          <ArrowLeft size={16} /> Back to home
        </Link>
        <ThemeToggle />
      </header>

      <section className="auth-card" aria-labelledby="login-title">
        <Link href="/" className="brand-lockup centered" aria-label="AVSAR home">
          <BrandLogo size={88} />
        </Link>

        <div className="auth-title">
          <span className="auth-icon">
            <KeyRound size={21} />
          </span>
          <h1 id="login-title">Welcome back</h1>
          <p>
            {step === "email" && "Sign in with a secure one-time passcode sent to your email."}
            {step === "otp" && `Enter the 6-digit code sent to ${email}`}
            {step === "success" && "Authentication verified successfully!"}
          </p>
        </div>

        {(error || configError) && (
          <div className="form-error" role="alert">
            {error || configError}
          </div>
        )}

        {successMsg && !error && (
          <div className="form-success" role="status" style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <CheckCircle2 size={16} />
            <span>{successMsg}</span>
          </div>
        )}

        {step === "email" && (
          <form className="auth-form" onSubmit={handleSendOtp}>
            <label>
              <span className="field-label">Email address</span>
              <div style={{ position: "relative" }}>
                <input
                  className="form-control"
                  type="email"
                  autoComplete="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  placeholder="student@example.edu"
                  required
                  disabled={busy}
                  style={{ paddingLeft: "36px" }}
                />
                <Mail
                  size={16}
                  style={{ position: "absolute", left: "12px", top: "50%", transform: "translateY(-50%)", color: "var(--text-muted, #738879)" }}
                />
              </div>
            </label>

            <button className="button button-primary full-width" type="submit" disabled={busy || loading}>
              {busy ? "Sending code…" : <>Send OTP Code <ArrowRight size={15} /></>}
            </button>
          </form>
        )}

        {step === "otp" && (
          <form className="auth-form" onSubmit={handleVerifyOtp}>
            <label>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span className="field-label">6-digit OTP code</span>
                <button
                  type="button"
                  onClick={() => { setStep("email"); setError(""); setSuccessMsg(""); }}
                  style={{ background: "none", border: "none", color: "var(--orange, #398956)", fontSize: "11px", cursor: "pointer", fontWeight: 700 }}
                >
                  Change email
                </button>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: "8px", marginTop: "4px" }}>
                {otp.map((digit, idx) => (
                  <input
                    key={idx}
                    ref={(el) => (otpInputRefs.current[idx] = el)}
                    className="form-control"
                    type="text"
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    maxLength={1}
                    value={digit}
                    onChange={(e) => handleOtpChange(idx, e.target.value)}
                    onKeyDown={(e) => handleOtpKeyDown(idx, e)}
                    disabled={busy}
                    aria-label={`Digit ${idx + 1}`}
                    style={{ textAlign: "center", fontSize: "18px", fontWeight: "700", minHeight: "48px", padding: "0" }}
                  />
                ))}
              </div>
            </label>

            <button
              className="button button-primary full-width"
              type="submit"
              disabled={busy || otp.join("").length !== 6}
            >
              {busy ? "Verifying…" : "Verify and Sign In"}
            </button>

            <div style={{ display: "flex", justifyContent: "center", alignItems: "center", marginTop: "12px", gap: "6px", fontSize: "12px" }}>
              <span style={{ color: "var(--text-muted, #738879)" }}>Didn&apos;t receive code?</span>
              <button
                type="button"
                onClick={handleResendOtp}
                disabled={cooldown > 0 || busy}
                style={{
                  background: "none",
                  border: "none",
                  color: cooldown > 0 ? "var(--text-muted, #a0aaa2)" : "var(--orange, #398956)",
                  cursor: cooldown > 0 ? "default" : "pointer",
                  fontWeight: "700",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "4px"
                }}
              >
                <RefreshCw size={13} className={busy ? "spin" : ""} />
                {cooldown > 0 ? `Resend in ${cooldown}s` : "Resend OTP"}
              </button>
            </div>
          </form>
        )}

        {step === "success" && (
          <div style={{ textAlign: "center", padding: "20px 0" }}>
            <p style={{ color: "var(--ink, #244331)", fontWeight: 600 }}>Welcome back! Loading your opportunities…</p>
          </div>
        )}

        <p className="auth-switch">
          New to AVSAR? <Link href={returnTo !== "/dashboard" ? `/signup?next=${encodeURIComponent(returnTo)}` : "/signup"}>Create an account</Link>
        </p>
      </section>
    </main>
  );
}
