"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowUpRight, BookmarkPlus, CalendarDays, MapPin, ShieldCheck, Sparkles } from "lucide-react";
import ProtectedWorkspace from "@/components/ProtectedWorkspace";
import Loading from "@/components/Loading";
import EligibilityBadge from "@/components/EligibilityBadge";
import TrustBadge from "@/components/TrustBadge";
import { api } from "@/services/api";
import { CATEGORY_LABELS } from "@/utils/constants";

function dateLabel(value) {
  if (!value) return "Not provided";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Not provided" : date.toLocaleDateString("en-IN", { day: "numeric", month: "long", year: "numeric" });
}

export default function OpportunityDetailPage() {
  const { id } = useParams();
  const [opportunity, setOpportunity] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [eligibility, setEligibility] = useState(null);
  const [checking, setChecking] = useState(false);
  const [trust, setTrust] = useState(null);
  const [checkingTrust, setCheckingTrust] = useState(false);

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true); setError("");
    try { setOpportunity(await api.opportunity(id)); }
    catch (requestError) { setError(requestError.message); }
    finally { setLoading(false); }
  }, [id]);
  useEffect(() => { load(); }, [load]);

  async function save() {
    setError(""); setNotice("");
    try { await api.createApplication(id); setNotice("Saved to your application tracker."); }
    catch (requestError) { setError(requestError.status === 409 ? "This opportunity is already in your tracker." : requestError.message); }
  }
  async function checkEligibility() {
    setChecking(true); setError("");
    try { setEligibility(await api.eligibility(id)); }
    catch (requestError) { setError(requestError.message); }
    finally { setChecking(false); }
  }
  async function checkTrust() {
    setCheckingTrust(true); setError("");
    try { setTrust(await api.trust(id)); }
    catch (requestError) { setError(requestError.message); }
    finally { setCheckingTrust(false); }
  }

  return <ProtectedWorkspace>
    <Link className="back-link" href="/opportunities">← Back to opportunities</Link>
    {loading ? <Loading label="Loading opportunity" /> : error && !opportunity ? <div className="inline-message error" role="alert">{error}</div> : opportunity && <>
      <div className="detail-layout">
        <article className="detail-main">
          <div className="detail-heading"><span className="eyebrow">{CATEGORY_LABELS[opportunity.category] || opportunity.category}</span><h1>{opportunity.title}</h1><p className="organization-name large">{opportunity.organization || opportunity.provider || "Organization not listed"}</p></div>
          <div className="detail-facts"><span><CalendarDays size={15} /> Deadline: {dateLabel(opportunity.deadline)}</span><span><MapPin size={15} /> {opportunity.location || "Location not specified"}</span><span>{opportunity.remote === true ? "Online" : opportunity.remote === false ? "On-site" : "Mode not specified"}</span></div>
          <section className="detail-section"><h2>About this opportunity</h2><p className="preserve-lines">{opportunity.description || "No description has been provided."}</p></section>
          <section className="detail-section"><h2>Eligibility requirements</h2>
            {opportunity.requirements?.confirmed ? <ul className="reason-list">
              {opportunity.requirements.graduation_years?.length > 0 && <li>Graduation year: {opportunity.requirements.graduation_years.join(", ")}</li>}
              {opportunity.requirements.degrees?.length > 0 && <li>Degree: {opportunity.requirements.degrees.join(", ")}</li>}
              {opportunity.requirements.branches?.length > 0 && <li>Branch: {opportunity.requirements.branches.join(", ")}</li>}
              {opportunity.requirements.min_cgpa != null && <li>Minimum CGPA: {opportunity.requirements.min_cgpa}</li>}
              {opportunity.requirements.locations?.length > 0 && <li>Location: {opportunity.requirements.locations.join(", ")}</li>}
              {opportunity.requirements.required_skills?.length > 0 && <li>Required skills: {opportunity.requirements.required_skills.join(", ")}</li>}
              {opportunity.requirements.preferred_skills?.length > 0 && <li>Preferred skills: {opportunity.requirements.preferred_skills.join(", ")}</li>}
            </ul> : <p>Eligibility criteria have not been confirmed by the source.</p>}
            <button className="button button-secondary" type="button" onClick={checkEligibility} disabled={checking}>{checking ? "Checking…" : "Check my eligibility"}</button>
            {eligibility && <div className="eligibility-result"><EligibilityBadge status={eligibility.api_status} /><p>{eligibility.summary}</p>{Number.isFinite(eligibility.score) && <p><strong>Criteria coverage: {Math.round(eligibility.score)}%</strong></p>}{eligibility.reasons?.length > 0 && <ul className="reason-list">{eligibility.reasons.map((reason, index) => <li key={`${reason}-${index}`}>{reason}</li>)}</ul>}{eligibility.missing_fields?.length > 0 && <p><strong>Profile information needed:</strong> {eligibility.missing_fields.join(", ")}</p>}</div>}
          </section>
          <section className="detail-section"><h2>Source and verification</h2><div className="source-details"><span>Source status</span><TrustBadge status={opportunity.verification_status} />{opportunity.source_url && <a href={opportunity.source_url} target="_blank" rel="noreferrer">Open original source <ArrowUpRight size={13} /></a>}</div><button className="button button-secondary" type="button" onClick={checkTrust} disabled={checkingTrust}><ShieldCheck size={15} />{checkingTrust ? "Checking source signals…" : "Review source signals"}</button>
            {trust && <div className="trust-report"><p><strong>Risk signals: {trust.risk_level || "Not assessed"}</strong>{Number.isFinite(trust.risk_score) && <> · score {trust.risk_score}/100</>}</p><p>Verification status: {trust.verification_status || "Unknown"}</p>{trust.evidence?.length > 0 ? <ul className="reason-list">{trust.evidence.map((item, index) => <li key={`${item.signal}-${index}`}><strong>{item.signal}</strong>{item.quote ? ` — “${item.quote}”` : ""}</li>)}</ul> : <p>No rule-based risk signals were found in the checked fields.</p>}<p className="disclaimer">{trust.disclaimer || "Risk signals are not a verified fraud classification. Confirm details with the original source."}</p></div>}
          </section>
        </article>
        <aside className="detail-aside"><div className="apply-card"><h2>Next steps</h2><p>{opportunity.benefit || "Review the source for application details and benefits."}</p>{opportunity.stipend != null && <p><strong>Stipend:</strong> {opportunity.stipend}</p>}<button type="button" className="button button-primary" onClick={save}><BookmarkPlus size={16} /> Save opportunity</button>{opportunity.application_url && <a className="button button-secondary external-link" href={opportunity.application_url} target="_blank" rel="noreferrer">Apply on source site <ArrowUpRight size={14} /></a>}<div className="side-note"><Sparkles size={16} /><p>Check the original source and eligibility details before sharing documents or paying any fee.</p></div></div></aside>
      </div>
      {notice && <div className="inline-message" role="status">{notice}</div>}
      {error && <div className="inline-message error" role="alert">{error}</div>}
    </>}
  </ProtectedWorkspace>;
}
