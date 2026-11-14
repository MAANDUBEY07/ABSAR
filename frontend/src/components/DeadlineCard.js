import Link from "next/link";
import { CalendarDays } from "lucide-react";

export default function DeadlineCard({ deadline, title, href }) {
  const date = deadline ? new Date(deadline) : null;
  const valid = date && !Number.isNaN(date.getTime());
  const days = valid ? Math.ceil((date.setHours(0, 0, 0, 0) - new Date().setHours(0, 0, 0, 0)) / 86400000) : null;
  const content = <><span className="deadline-icon"><CalendarDays size={17} aria-hidden="true" /></span><span className="deadline-copy"><strong>{title || "Application deadline"}</strong><span>{valid ? date.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" }) : "Date not provided"}</span></span>{days !== null && <span className={`days-left ${days <= 3 ? "urgent" : ""}`}>{days < 0 ? "Passed" : days === 0 ? "Today" : `${days} days`}</span>}</>;
  return href ? <Link className="deadline-card" href={href}>{content}</Link> : <div className="deadline-card">{content}</div>;
}
