import Link from "next/link";
import { ArrowUpRight, Bookmark, CalendarDays, MapPin, Wallet, BriefcaseBusiness, GraduationCap, Trophy, FlaskConical, Handshake } from "lucide-react";
import TrustBadge from "@/components/TrustBadge";
import { CATEGORY_LABELS } from "@/utils/constants";

function dateLabel(value) {
  if (!value) return "Deadline not provided";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Deadline not provided" : date.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

function CategoryIcon({ category }) {
  const Icon = category === "SCHOLARSHIP" ? GraduationCap : category === "HACKATHON" ? Trophy : category === "RESEARCH" ? FlaskConical : category === "FELLOWSHIP" ? Handshake : BriefcaseBusiness;
  return <Icon size={21} />;
}

export default function OpportunityCard({ opportunity, saved = false, onSave }) {
  const category = CATEGORY_LABELS[opportunity.category] || opportunity.category || "Opportunity";
  return (
    <article className="opportunity-card">
      <div className="card-topline"><span className={`card-category-icon ${String(opportunity.category || "other").toLowerCase()}`}><CategoryIcon category={opportunity.category} /></span><span className="category-label">{category}</span><button className={`bookmark-button ${saved ? "active" : ""}`} onClick={() => onSave?.(opportunity)} aria-label={saved ? "Unsave opportunity" : "Save opportunity"}><Bookmark size={17} fill={saved ? "currentColor" : "none"} /></button></div>
      <h3 className="opportunity-title">{opportunity.title}</h3>
      <p className="organization-name">{opportunity.organization}</p>
      <div className="opportunity-meta"><span><MapPin size={14} />{opportunity.location || "Location not specified"}</span><span><Wallet size={14} />{opportunity.stipend || "Compensation not listed"}</span></div>
      <div className="card-badges"><TrustBadge status={opportunity.trust?.status} /></div>
      <div className="card-footer"><span className="deadline-label"><CalendarDays size={14} />{dateLabel(opportunity.deadline)}</span><Link href={`/opportunities/${opportunity.id}`} className="text-link">View details <ArrowUpRight size={15} /></Link></div>
      <p className="demo-disclaimer">{opportunity.source_name?.toLowerCase().includes("demo") || opportunity.source_url?.includes("example.com") ? "Sample listing · not a real opportunity" : "Source-provided listing · review details"}</p>
    </article>
  );
}
