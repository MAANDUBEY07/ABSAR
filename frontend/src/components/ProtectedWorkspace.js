"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import Navbar from "@/components/Navbar";
import Sidebar from "@/components/Sidebar";
import Loading from "@/components/Loading";

export default function ProtectedWorkspace({ children }) {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  if (loading || !user) return <div className="protected-loading"><Loading /> <span>Checking your session…</span></div>;

  return (
    <div className="app-shell">
      <Sidebar open={menuOpen} onClose={() => setMenuOpen(false)} />
      <div className="main-column">
        <Navbar menuOpen={menuOpen} onMenuClick={() => setMenuOpen((open) => !open)} />
        <main className="page-content">{children}</main>
        <footer className="footer"><span>AVSAR</span><span>Discover more. Apply smarter.</span><span className="footer-right">Always verify details with the source</span></footer>
      </div>
    </div>
  );
}
