"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft, UserRoundPlus } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import ThemeToggle from "@/components/ThemeToggle";
import BrandLogo from "@/components/BrandLogo";
import { returnToFromSearch } from "@/utils/returnTo.mjs";

export default function SignupPage() {
  const { user, loading, error: configError, signUp } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [returnTo, setReturnTo] = useState("/dashboard");
  useEffect(() => {
    const destination = returnToFromSearch(window.location.search);
    setReturnTo(destination);
    if (!loading && user) router.replace(destination);
  }, [loading, user, router]);
  async function submit(event) {
    event.preventDefault(); setError(""); setBusy(true);
    try {
      const result = await signUp({ email, password });
      if (result.confirmationRequired) setConfirmation(true);
      else router.replace(returnTo);
    } catch (requestError) { setError(requestError.message || "Unable to create your account."); }
    finally { setBusy(false); }
  }
  return (
    <main className="auth-page">
      <ThemeToggle className="auth-theme-toggle" />
      <Link href="/" className="back-link"><ArrowLeft size={15} /> Back to AVSAR</Link>
      <section className="auth-card" aria-labelledby="signup-title">
        <Link href="/" className="brand-lockup centered" aria-label="AVSAR home"><BrandLogo size={88} /></Link>
        <div className="auth-title"><span className="auth-icon"><UserRoundPlus size={21} /></span><h1 id="signup-title">Create your account</h1><p>One profile for your next opportunity.</p></div>
        {confirmation && <p className="form-success" role="status">Check your inbox to confirm your email, then sign in.</p>}
        {(error || configError) && <p className="form-error" role="alert">{error || configError}</p>}
        {!confirmation && <form className="auth-form" onSubmit={submit}>
          <label><span className="field-label">Email address</span><input className="form-control" type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} required /></label>
          <label><span className="field-label">Password</span><input className="form-control" type="password" autoComplete="new-password" value={password} onChange={(event) => setPassword(event.target.value)} required minLength={12} aria-describedby="password-help" /><small id="password-help">Use at least 12 characters.</small></label>
          <button className="button button-primary full-width" type="submit" disabled={busy || loading}>{busy ? "Creating account…" : "Create account"}</button>
        </form>}
        <p className="auth-switch">Already registered? <Link href={`/login?next=${encodeURIComponent(returnTo)}`}>Sign in</Link></p>
      </section>
    </main>
  );
}
