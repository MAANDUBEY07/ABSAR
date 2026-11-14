"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { CalendarDays, FileText, LayoutDashboard, Search, UserRound, ClipboardList, ArrowUpRight, ShieldCheck } from "lucide-react";

const items = [
  { label: "Home", href: "/dashboard", Icon: LayoutDashboard },
  { label: "Discover opportunities", href: "/opportunities", Icon: Search },
  { label: "Resume analyzer", href: "/resume", Icon: FileText },
  { label: "My applications", href: "/applications", Icon: ClipboardList },
  { label: "Deadline calendar", href: "/calendar", Icon: CalendarDays },
  { label: "My profile", href: "/profile", Icon: UserRound }
];

export default function Sidebar({ open = false, onClose = () => {} }) {
  const pathname = usePathname();
  return <>
    {open && <button className="mobile-overlay" onClick={onClose} aria-label="Close navigation" />}
    <aside id="workspace-sidebar" className={`sidebar ${open ? "sidebar-open" : ""}`} aria-label="Workspace navigation">
      <div className="sidebar-brand"><Link href="/dashboard" className="brand-lockup"><span className="sidebar-logo">avsar<ArrowUpRight size={14} /></span><small>YOUR OPPORTUNITY DESK</small></Link></div>
      <div className="sidebar-label">YOUR WORKSPACE</div>
      <nav className="side-nav">
        {items.map(({ label, href, Icon }) => { const selected = pathname === href || (href === "/opportunities" && pathname.startsWith("/opportunities/")); return <Link key={href} href={href} onClick={onClose} className={`side-link ${selected ? "selected" : ""}`} aria-current={selected ? "page" : undefined}><Icon size={18} aria-hidden="true" /><span>{label}</span></Link>; })}
      </nav>
      <div className="sidebar-bottom">
        <div className="help-card"><div className="help-symbol"><ShieldCheck size={18} /></div><strong>Stay safe while applying</strong><p>Check the original source before sharing documents or paying application fees.</p><a href="https://www.cybercrime.gov.in/" target="_blank" rel="noreferrer">Visit cybercrime portal <ArrowUpRight size={12} /></a></div>
        <div className="sidebar-version">AVSAR · STUDENT OPPORTUNITY PLATFORM</div>
      </div>
    </aside>
  </>;
}
