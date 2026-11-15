"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft, LockKeyhole } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import ThemeToggle from "@/components/ThemeToggle";

export default function LoginPage() {
  const { user, loading, error: configError, signIn } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (!loading && user) router.replace("/dashboard"); }, [loading, user, router]);
  async function submit(event) {
    event.preventDefault(); setError(""); setBusy(true);
    try { await signIn({ email, password }); router.replace("/dashboard"); }
    catch (requestError) { setError(requestError.message || "Unable to sign in."); }
    finally { setBusy(false); }
  }
  return (
    <main className="auth-page">
      <ThemeToggle className="auth-theme-toggle" />
      <Link href="/" className="back-link"><ArrowLeft size={15} /> Back to AVSAR</Link>
      <section className="auth-card" aria-labelledby="login-title">
        <Link href="/" className="brand-lockup centered"><span className="brand-symbol">A</span><span>avsar<small>YOUR OPPORTUNITY DESK</small></span></Link>
        <div className="auth-title"><span className="auth-icon"><LockKeyhole size={21} /></span><h1 id="login-title">Welcome back</h1><p>Sign in to manage your opportunities.</p></div>
        {(error || configError) && <p className="form-error" role="alert">{error || configError}</p>}
        <form className="auth-form" onSubmit={submit}>
          <label><span className="field-label">Email address</span><input className="form-control" type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} required /></label>
          <label><span className="field-label">Password</span><input className="form-control" type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required minLength={8} /></label>
          <button className="button button-primary full-width" type="submit" disabled={busy || loading}>{busy ? "Signing in…" : "Sign in"}</button>
        </form>
        <p className="auth-switch">New to AVSAR? <Link href="/signup">Create an account</Link></p>
      </section>
    </main>
  );
}
