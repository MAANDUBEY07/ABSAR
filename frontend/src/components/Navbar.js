"use client";

import Link from "next/link";
import { Search, Bell, ArrowUpRight, Menu } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";

export default function Navbar({ onMenuClick = () => {} }) {
  const { user } = useAuth();
  const email = user?.email || "demo@student.in";
  const initials = (user?.user_metadata?.full_name || email).slice(0, 1).toUpperCase();
  return (
    <header className="workspace-header">
      <button className="workspace-menu-button" type="button" onClick={onMenuClick} aria-label="Open navigation"><Menu size={19} /></button>
      <form className="workspace-search" action="/opportunities" method="GET">
        <Search size={17} />
        <input name="q" placeholder="Search opportunities, skills, organisations..." aria-label="Search opportunities" />
        <button type="submit">Search</button>
      </form>
      <div className="workspace-actions">
        <span className="workspace-demo-label"><span /> DEMO MODE</span>
        <button className="header-notice" type="button" aria-label="Notifications"><Bell size={18} /><i /></button>
        <Link href="/profile" className="workspace-user" title={email}><span className="workspace-avatar">{initials}</span><span className="workspace-user-name">My profile</span><ArrowUpRight size={13} /></Link>
      </div>
    </header>
  );
}
