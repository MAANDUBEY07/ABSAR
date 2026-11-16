"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { CalendarDays, FileText, LayoutDashboard, Search, UserRound, ClipboardList, ArrowUpRight, ShieldCheck } from "lucide-react";
import BrandLogo from "@/components/BrandLogo";

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
  const sidebarRef = useRef(null);
  const [mobile, setMobile] = useState(false);

  useEffect(() => {
    const query = window.matchMedia("(max-width: 820px)");
    const update = () => setMobile(query.matches);
    update();
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);

  useEffect(() => {
    if (!open || !mobile) return undefined;
    const previousFocus = document.activeElement;
    const panel = sidebarRef.current;
    const focusable = () => Array.from(panel?.querySelectorAll('a[href], button:not(:disabled)') || []);
    const first = focusable()[0];
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    first?.focus();

    function onKeyDown(event) {
      if (event.key === "Escape") { event.preventDefault(); onClose(); return; }
      if (event.key !== "Tab") return;
      const elements = focusable();
      if (!elements.length) return;
      const firstElement = elements[0];
      const lastElement = elements[elements.length - 1];
      if (event.shiftKey && (document.activeElement === firstElement || !panel.contains(document.activeElement))) {
        event.preventDefault(); lastElement.focus();
      } else if (!event.shiftKey && (document.activeElement === lastElement || !panel.contains(document.activeElement))) {
        event.preventDefault(); firstElement.focus();
      }
    }

    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = previousOverflow;
      if (previousFocus instanceof HTMLElement && previousFocus.isConnected) previousFocus.focus();
    };
  }, [mobile, onClose, open]);

  return <>
    {open && mobile && <button className="mobile-overlay" onClick={onClose} aria-label="Close navigation" tabIndex={-1} />}
    <aside ref={sidebarRef} id="workspace-sidebar" className={`sidebar ${open ? "sidebar-open" : ""}`} aria-label="Workspace navigation" role={mobile && open ? "dialog" : undefined} aria-modal={mobile && open ? "true" : undefined} aria-hidden={mobile && !open ? "true" : undefined} inert={mobile && !open}>
      <div className="sidebar-brand"><Link href="/dashboard" className="brand-lockup sidebar-logo" aria-label="AVSAR dashboard"><BrandLogo size={58} /></Link></div>
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
