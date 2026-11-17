import Link from "next/link";
import { ArrowUpRight, Bookmark, BookmarkCheck, LoaderCircle, CalendarDays, MapPin, Wallet, BriefcaseBusiness, GraduationCap, Trophy, FlaskConical, Handshake, Laptop, Gift, Landmark, Lightbulb, Rocket } from "lucide-react";
import TrustBadge from "@/components/TrustBadge";
import { CATEGORY_LABELS } from "@/utils/constants";
import { opportunityModeLabel } from "@/utils/opportunity-mode.mjs";

function dateLabel(value) {
  if (!value) return "Deadline not provided";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Deadline not provided" : date.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

const categoryIcons = {
  scholarship: GraduationCap, internship: BriefcaseBusiness, job: Laptop,
  government_scheme: Landmark, fellowship: Handshake, apprenticeship: Laptop,
  hackathon: Trophy, coding_competition: Lightbulb, innovation_challenge: Rocket,
  startup_challenge: Rocket, grant: Gift, research: FlaskConical,
};

export default function OpportunityCard({ opportunity, saved = false, saving = false, onSave, matchScore }) {
  const category = String(opportunity.category || "other").toLowerCase();
  const Icon = categoryIcons[category] || BriefcaseBusiness;
  const organization = opportunity.organization || opportunity.provider || "Organization not listed";
  const compensation = opportunity.stipend == null ? "Compensation not listed" : `${opportunity.stipend} stipend`;
  const mode = opportunityModeLabel(opportunity);
  return (
    <article className="opportunity-card">
      <div className="card-topline">
        <span className={`card-category-icon ${category}`}><Icon size={19} aria-hidden="true" /></span>
        <span className="category-label">{CATEGORY_LABELS[category] || category.replaceAll("_", " ")}</span>
        {onSave && <button className={`bookmark-button ${saved ? "active" : ""}`} type="button" onClick={() => onSave(opportunity)} aria-label={saved ? `${opportunity.title} is saved in applications` : saving ? `Saving ${opportunity.title}` : `Save ${opportunity.title}`} title={saved ? "Saved to your applications" : "Save opportunity"} aria-pressed={saved} disabled={saved || saving}>{saving ? <LoaderCircle className="spin" size={17} aria-hidden="true" /> : saved ? <BookmarkCheck size={17} aria-hidden="true" /> : <Bookmark size={17} aria-hidden="true" />}</button>}
      </div>
      <h3 className="opportunity-title">{opportunity.title || "Untitled opportunity"}</h3>
      <p className="organization-name">{organization}</p>
      <div className="opportunity-meta">
        <span><MapPin size={14} aria-hidden="true" />{opportunity.location || "Location not specified"}</span>
        <span><Wallet size={14} aria-hidden="true" />{compensation}</span>
        <span>{mode}</span>
      </div>
      <div className="card-badges"><TrustBadge status={opportunity.verification_status} />{Number.isFinite(matchScore) && <span className="badge badge-neutral">Match score {Math.round(matchScore)}%</span>}</div>
      <div className="card-footer">
        <span className="deadline-label"><CalendarDays size={14} aria-hidden="true" />{dateLabel(opportunity.deadline)}</span>
        <Link href={`/opportunities/${encodeURIComponent(opportunity.id)}`} className="text-link">View details <ArrowUpRight size={15} aria-hidden="true" /></Link>
      </div>
    </article>
  );
}
