"use client";

import { useState } from "react";
import Link from "next/link";
import { Search, LogOut, Menu, Bell } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import ThemeToggle from "@/components/ThemeToggle";

export default function Navbar({ onMenuClick = () => {}, menuOpen = false }) {
  const { user, signOut } = useAuth();
  const [loggingOut, setLoggingOut] = useState(false);
  const email = user?.email || "Student account";
  const displayName = user?.user_metadata?.full_name || user?.user_metadata?.name || user?.email || "Student account";
  const initials = (user?.user_metadata?.full_name || user?.email || "S").slice(0, 1).toUpperCase();
  async function handleSignOut() {
    setLoggingOut(true);
    await signOut();
    window.location.assign("/login");
  }
  return (
    <header className="workspace-header">
      <button className="workspace-menu-button" type="button" onClick={onMenuClick} aria-label="Toggle navigation" aria-expanded={menuOpen} aria-controls="workspace-sidebar"><Menu size={19} /></button>
      <form className="workspace-search" action="/opportunities" method="GET" role="search">
        <Search size={17} aria-hidden="true" />
        <input name="search" placeholder="Search opportunities, skills, organisations…" aria-label="Search opportunities" />
        <button type="submit">Search</button>
      </form>
      <div className="workspace-actions">
        <Link href="/dashboard#notifications" className="header-notice" aria-label="View notifications"><Bell size={18} /></Link>
        <ThemeToggle />
        <Link href="/profile" className="workspace-user" title={email}><span className="workspace-avatar" aria-hidden="true">{initials}</span><span className="workspace-user-name">{displayName}</span></Link>
        <button className="button button-secondary navbar-signout" type="button" onClick={handleSignOut} disabled={loggingOut}>{loggingOut ? "Signing out…" : <><LogOut size={15} /> Sign out</>}</button>
      </div>
    </header>
  );
}
