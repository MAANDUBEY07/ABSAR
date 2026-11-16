"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import Navbar from "@/components/Navbar";
import Sidebar from "@/components/Sidebar";
import Loading from "@/components/Loading";
import BrandLogo from "@/components/BrandLogo";
import { safeReturnTo } from "@/utils/returnTo.mjs";

export default function ProtectedWorkspace({ children }) {
  const { user, loading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const [menuOpen, setMenuOpen] = useState(false);
  const closeMenu = useCallback(() => setMenuOpen(false), []);
  const toggleMenu = useCallback(() => setMenuOpen((open) => !open), []);

  useEffect(() => {
    if (!loading && !user) {
      const currentPath = `${pathname}${window.location.search}${window.location.hash}`;
      router.replace(`/login?next=${encodeURIComponent(safeReturnTo(currentPath))}`);
    }
  }, [loading, user, pathname, router]);

  if (loading) return <div className="protected-loading" role="status" aria-live="polite"><Loading label="Checking your session" /><span>Checking your session…</span></div>;
  if (!user) return <div className="protected-loading"><Loading label="Redirecting to sign in" /><p>You need to sign in to open this page.</p><Link className="button button-primary" href={`/login?next=${encodeURIComponent(safeReturnTo(`${pathname}${typeof window !== "undefined" ? window.location.search : ""}`))}`}>Continue to sign in</Link></div>;

  return (
    <div className="app-shell">
      <Sidebar open={menuOpen} onClose={closeMenu} />
      <div className="main-column">
        <Navbar menuOpen={menuOpen} onMenuClick={toggleMenu} />
        <main className="page-content">{children}</main>
        <footer className="footer"><BrandLogo size={43} /><span>Discover more. Apply smarter.</span><span className="footer-right">Always verify details with the source</span></footer>
      </div>
    </div>
  );
}
