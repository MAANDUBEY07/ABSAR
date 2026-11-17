"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  AlertCircle,
  AlertTriangle,
  ArrowUpRight,
  BookmarkCheck,
  BookmarkPlus,
  CalendarDays,
  CheckCircle2,
  Globe,
  LoaderCircle,
  MapPin,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import ProtectedWorkspace from "@/components/ProtectedWorkspace";
import Loading from "@/components/Loading";
import EligibilityBadge from "@/components/EligibilityBadge";
import TrustBadge from "@/components/TrustBadge";
import { api } from "@/services/api";
import { opportunityModeLabel } from "@/utils/opportunity-mode.mjs";
import { CATEGORY_LABELS } from "@/utils/constants";
import { demoOpportunities } from "@/utils/demo-data";

function dateLabel(value) {
  if (!value) return "Not provided";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "Not provided"
    : date.toLocaleDateString("en-IN", { day: "numeric", month: "long", year: "numeric" });
}

export default function OpportunityDetailPage() {
  const { id } = useParams();
  const demoOpportunity = demoOpportunities.find((item) => item.id === id) || null;
  const [opportunity, setOpportunity] = useState(demoOpportunity);
  const [loading, setLoading] = useState(!demoOpportunity);
  const [error, setError] = useState("");
  const [isDemo, setIsDemo] = useState(Boolean(demoOpportunity));
  const [notice, setNotice] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [eligibility, setEligibility] = useState(null);
  const [checking, setChecking] = useState(false);
  const [trust, setTrust] = useState(null);
  const [checkingTrust, setCheckingTrust] = useState(false);
  const [signalsExpanded, setSignalsExpanded] = useState(false);
  const [showManualInput, setShowManualInput] = useState(false);
  const [manualText, setManualText] = useState("");

  const load = useCallback(async () => {
    if (!id) return;
    setError("");
    const sample = demoOpportunities.find((item) => item.id === id);
    if (sample) {
      setOpportunity(sample);
      setIsDemo(true);
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const opp = await api.opportunity(id);
      setOpportunity(opp);
      setIsDemo(false);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  async function save() {
    if (saving || saved) return;
    setError("");
    setNotice("");
    if (isDemo) {
      setError("This sample listing cannot be saved. Open a live listing to add it to your tracker.");
      return;
    }
    setSaving(true);
    try {
      await api.createApplication(id);
      setSaved(true);
      setNotice("Saved to your application tracker.");
    } catch (requestError) {
      if (requestError.status === 409) {
        setSaved(true);
        setNotice("This opportunity is already in your tracker.");
      } else {
        setError(requestError.message);
      }
    } finally {
      setSaving(false);
    }
  }

  async function checkEligibility(customText = null) {
    setChecking(true);
    setError("");
    if (isDemo) {
      setError("Eligibility checks are unavailable for sample listings. Open a live listing to check eligibility.");
      setChecking(false);
      return;
    }
    try {
      const payload = customText ? { user_description: customText } : {};
      const result = await api.eligibility(id, payload);
      setEligibility(result);
      if (result.source_summary || result.requirements) {
        setOpportunity((prev) => ({
          ...prev,
          source_summary: result.source_summary || prev?.source_summary,
          requirements: result.requirements || prev?.requirements,
        }));
      }
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setChecking(false);
    }
  }

  async function checkTrust() {
    setCheckingTrust(true);
    setError("");
    if (isDemo) {
      setError("Source checks are unavailable for sample listings. Open a live listing to review source signals.");
      setCheckingTrust(false);
      return;
    }
    try {
      setTrust(await api.analyzeTrust(id));
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setCheckingTrust(false);
    }
  }

  const sourceSummary = opportunity?.source_summary || eligibility?.source_summary || null;
  let sourceDomain = "";
  try {
    const rawUrl = opportunity?.source_url || opportunity?.application_url;
    if (rawUrl) {
      sourceDomain = new URL(rawUrl).hostname.replace(/^www\./, "");
    }
  } catch {}

  const statusExplanations = {
    VERIFIED: "Official source verified against trusted registry or canonical domain.",
    UNVERIFIED: "Listing is unverified. Claims have not been verified against an official government or institutional registry.",
    SUSPICIOUS: "Elevated risk signals detected. Review all terms carefully before applying.",
    UNKNOWN: "Source verification has not been determined yet.",
    EXPIRED: "This listing has passed its published deadline.",
  };
  const verificationStatus = String(trust?.verification_status || opportunity?.verification_status || "UNKNOWN").toUpperCase();
  const statusExplanation = statusExplanations[verificationStatus] || statusExplanations.UNKNOWN;
  const hasRiskSignals = Boolean(trust?.evidence && trust.evidence.length > 0);

  return (
    <ProtectedWorkspace>
      <Link className="back-link" href="/opportunities">
        ← Back to opportunities
      </Link>
      {loading ? (
        <Loading label="Loading opportunity" />
      ) : error && !opportunity ? (
        <div className="empty-state" role="alert">
          <AlertCircle size={26} />
          <h2>Could not load this opportunity</h2>
          <p>{error}</p>
          <button className="button button-primary" type="button" onClick={load}>
            <RefreshCw size={15} /> Try again
          </button>
        </div>
      ) : (
        opportunity && (
          <>
            <div className="detail-layout">
              <article className="detail-main">
                <div className="detail-heading">
                  <span className="eyebrow">
                    {CATEGORY_LABELS[opportunity.category] || opportunity.category}
                  </span>
                  <h1>{opportunity.title}</h1>
                  <p className="organization-name large">
                    {opportunity.organization || opportunity.provider || "Organization not listed"}
                  </p>
                </div>
                <div className="detail-facts">
                  <span>
                    <CalendarDays size={15} /> Deadline: {dateLabel(opportunity.deadline)}
                  </span>
                  <span>
                    <MapPin size={15} /> {opportunity.location || "Location not specified"}
                  </span>
                  <span>
                    {opportunityModeLabel(opportunity)}
                  </span>
                </div>
                {/* PRIORITY 1: Readable Source Summary */}
                <section className="detail-section source-summary-section">
                  <div className="section-title-row" style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "8px" }}>
                    <h2>About this opportunity</h2>
                    {sourceSummary?.source_language && (
                      <span className="badge badge-neutral">
                        Source language: {sourceSummary.source_language === "de" ? "German" : "English"}
                      </span>
                    )}
                  </div>
                  <p className="preserve-lines summary-overview">
                    {sourceSummary?.overview || opportunity.description || "No overview provided."}
                  </p>

                  <div className="summary-block">
                    <h3>Who should apply or participate</h3>
                    <p>{sourceSummary?.who_should_apply || "Students, recent graduates, or candidates meeting the stated requirements."}</p>
                  </div>

                  <div className="summary-block">
                    <h3>Key requirements</h3>
                    {sourceSummary?.key_requirements?.length > 0 ? (
                      <ul className="reason-list">
                        {sourceSummary.key_requirements.map((req, idx) => (
                          <li key={idx}>{req}</li>
                        ))}
                      </ul>
                    ) : opportunity.requirements?.confirmed ? (
                      <ul className="reason-list">
                        {opportunity.requirements.degrees?.length > 0 && <li>Degree: {opportunity.requirements.degrees.join(", ")}</li>}
                        {opportunity.requirements.branches?.length > 0 && <li>Branch: {opportunity.requirements.branches.join(", ")}</li>}
                        {opportunity.requirements.min_experience_months && <li>Experience: Minimum {opportunity.requirements.min_experience_months} months</li>}
                        {opportunity.requirements.min_cgpa != null && <li>Minimum CGPA: {opportunity.requirements.min_cgpa}</li>}
                        {opportunity.requirements.locations?.length > 0 && <li>Location: {opportunity.requirements.locations.join(", ")}</li>}
                      </ul>
                    ) : (
                      <p style={{ color: "var(--muted)", margin: "4px 0" }}>
                        Eligibility criteria have not been confirmed by the source. Review original source details below.
                      </p>
                    )}
                  </div>

                  {((opportunity.requirements?.required_skills?.length > 0) || (opportunity.requirements?.preferred_skills?.length > 0)) && (
                    <div className="summary-block">
                      <h3>Skills & technical competencies</h3>
                      <div className="skills-chip-container">
                        {opportunity.requirements.required_skills?.map((s) => (
                          <span key={s} className="skill-chip required" title="Mandatory core skill">{s}</span>
                        ))}
                        {opportunity.requirements.preferred_skills?.map((s) => (
                          <span key={s} className="skill-chip preferred" title="Preferred / nice-to-have skill">{s} (preferred)</span>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="summary-block">
                    <h3>Important dates & deadlines</h3>
                    <ul className="reason-list">
                      <li>Application deadline: {dateLabel(opportunity.deadline)}</li>
                      {sourceSummary?.important_dates?.map((d, idx) => (
                        <li key={idx}>{d}</li>
                      ))}
                    </ul>
                  </div>

                  <div className="summary-block">
                    <h3>Application & submission instructions</h3>
                    <p>{sourceSummary?.application_instructions || "Submit your application directly through the official provider link."}</p>
                  </div>
                </section>

                {/* PRIORITY 2: Complete Eligibility Workflow */}
                <section className="detail-section eligibility-check-section">
                  <h2>Eligibility check</h2>
                  <p style={{ margin: "4px 0 12px", color: "var(--muted)", fontSize: "11px" }}>
                    AVSAR deterministically evaluates your saved profile against evidence-backed criteria extracted from the source.
                  </p>

                  <div className="eligibility-actions">
                    <button
                      className="button button-primary"
                      type="button"
                      onClick={() => checkEligibility()}
                      disabled={checking}
                    >
                      {checking ? (
                        <>
                          <LoaderCircle className="spin" size={15} /> Checking & analyzing source…
                        </>
                      ) : (
                        <>
                          <Sparkles size={15} /> Check my eligibility
                        </>
                      )}
                    </button>
                    <button
                      className="button button-secondary"
                      type="button"
                      onClick={() => setShowManualInput(!showManualInput)}
                    >
                      {showManualInput ? "Hide manual text review" : "Review with manual text input"}
                    </button>
                  </div>

                  {/* Fallback Manual Review Input */}
                  {showManualInput && (
                    <div className="manual-review-card">
                      <h4>Review requirements with your own text</h4>
                      <p>If automated extraction could not fetch the source, paste the requirement or qualification text from the opportunity source:</p>
                      <textarea
                        className="manual-review-textarea"
                        rows={3}
                        placeholder="Paste requirement text here (e.g. 'Requires B.Tech Computer Science, 2 years Python experience, German C1')..."
                        value={manualText}
                        onChange={(e) => setManualText(e.target.value)}
                      />
                      <button
                        className="button button-secondary button-sm"
                        type="button"
                        disabled={!manualText.trim() || checking}
                        onClick={() => checkEligibility(manualText)}
                        style={{ justifySelf: "start" }}
                      >
                        Evaluate with user-provided text
                      </button>
                    </div>
                  )}

                  {eligibility && (
                    <div className="eligibility-result" style={{ marginTop: "16px" }}>
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between",
                          gap: "10px",
                          marginBottom: "8px",
                        }}
                      >
                        <EligibilityBadge status={eligibility.api_status} />
                        {Number.isFinite(eligibility.score) && (
                          <span style={{ fontSize: "11px", fontWeight: 800, color: "var(--green)" }}>
                            Criteria coverage: {Math.round(eligibility.score)}%
                          </span>
                        )}
                      </div>

                      <p
                        style={{
                          margin: "4px 0 8px",
                          fontSize: "11px",
                          color: "var(--ink)",
                          fontWeight: 700,
                        }}
                      >
                        {eligibility.summary}
                      </p>

                      {/* If missing opportunity criteria, advise clearly */}
                      {(eligibility.has_missing_opportunity_criteria ||
                        eligibility.api_status === "CANNOT_DETERMINE") && (
                        <div className="criteria-warning-banner">
                          <AlertTriangle size={15} style={{ flexShrink: 0 }} />
                          <span>
                            Eligibility criteria could not be confirmed automatically by the source. Please review the original source listing or use the manual text review above.
                          </span>
                        </div>
                      )}

                      {/* Passed criteria */}
                      {eligibility.passed_criteria?.length > 0 && (
                        <div className="criteria-group">
                          <h4 className="criteria-heading success">
                            <CheckCircle2 size={13} /> Passed criteria ({eligibility.passed_count ?? eligibility.passed_criteria.length})
                          </h4>
                          <ul className="criteria-items">
                            {eligibility.passed_criteria.map((c, i) => (
                              <li key={i} className="criteria-item">
                                <strong>{c.field || "Requirement"}:</strong>{" "}
                                {c.criterion_description || c.reason || "Satisfied"}
                                {c.actual_value !== undefined && c.actual_value !== null && (
                                  <span className="criteria-actual">
                                    {" "}
                                    (Your profile: {String(c.actual_value)})
                                  </span>
                                )}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {/* Failed criteria */}
                      {eligibility.failed_criteria?.length > 0 && (
                        <div className="criteria-group">
                          <h4 className="criteria-heading danger">
                            <AlertCircle size={13} /> Failed criteria ({eligibility.failed_count ?? eligibility.failed_criteria.length})
                          </h4>
                          <ul className="criteria-items">
                            {eligibility.failed_criteria.map((c, i) => (
                              <li key={i} className="criteria-item">
                                <strong>{c.field || "Requirement"}:</strong>{" "}
                                {c.reason || c.criterion_description || "Did not satisfy condition"}
                                {c.actual_value !== undefined && c.actual_value !== null && (
                                  <span className="criteria-actual">
                                    {" "}
                                    (Your profile: {String(c.actual_value)})
                                  </span>
                                )}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {/* Missing student info / criteria */}
                      {(eligibility.missing_fields?.length > 0 ||
                        eligibility.missing_criteria?.length > 0) && (
                        <div className="criteria-group">
                          <h4 className="criteria-heading warning">
                            <AlertTriangle size={13} /> Profile information needed ({eligibility.missing_count ?? eligibility.missing_fields?.length ?? 0})
                          </h4>
                          <p className="missing-hint">
                            Add to your profile to complete eligibility check:{" "}
                            <strong>
                              {(
                                eligibility.missing_fields ||
                                eligibility.missing_criteria?.map((c) => c.field)
                              ).join(", ")}
                            </strong>
                          </p>
                          <Link className="text-link" href="/profile">
                            Update your profile →
                          </Link>
                        </div>
                      )}

                      {eligibility.reasons?.length > 0 &&
                        !eligibility.passed_criteria?.length &&
                        !eligibility.failed_criteria?.length && (
                          <ul className="reason-list">
                            {eligibility.reasons.map((reason, index) => (
                              <li key={`${reason}-${index}`}>{reason}</li>
                            ))}
                          </ul>
                        )}
                    </div>
                  )}
                </section>

                {/* MEM 3: Redesigned Source & Verification Section */}
                <section className="detail-section source-verification-section">
                  <h2>Source and verification</h2>

                  {/* Part A: Source Information */}
                  <div className="source-info-card">
                    <div className="source-info-main">
                      <div className="source-info-header">
                        <span className="source-domain-badge">
                          <Globe size={13} /> {sourceDomain || "Source website"}
                        </span>
                        <TrustBadge
                          status={verificationStatus}
                          report={trust}
                        />
                      </div>
                      <p className="source-status-explanation">
                        {statusExplanation}
                      </p>
                    </div>
                    {opportunity.source_url && (
                      <a
                        href={opportunity.source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="source-external-link"
                        aria-label={`Open original source at ${sourceDomain || "source website"}`}
                      >
                        <span>Open original source</span>
                        <ArrowUpRight size={14} style={{ flexShrink: 0 }} />
                      </a>
                    )}
                  </div>

                  {/* Part B: Risk Assessment */}
                  <div className="risk-assessment-card">
                    <div className="risk-metric-header">
                      <div className="risk-metric-title">
                        <ShieldAlert size={16} style={{ color: hasRiskSignals ? "var(--orange)" : "var(--green)" }} />
                        <strong>Risk assessment</strong>
                      </div>
                      {Number.isFinite(trust?.risk_score) && (
                        <span className="risk-score-pill">
                          Risk score: {trust.risk_score}/100
                        </span>
                      )}
                    </div>
                    <p className="risk-explanation-text">
                      {hasRiskSignals
                        ? `${trust.evidence.length} potential risk signal(s) detected during rule-based inspection. Review details below.`
                        : "No rule-based risk indicators were detected in the fields checked."}
                    </p>
                    <div className="risk-disclaimer-text">
                      Note: Rule-based risk checks are safety indicators and do not represent verified proof of legitimacy or fraud.
                    </div>

                    {/* Part C: Expandable Source Signals */}
                    <div className="signals-toggle-container">
                      <button
                        className="button button-secondary button-sm"
                        type="button"
                        onClick={() => {
                          if (!trust && !checkingTrust) checkTrust();
                          setSignalsExpanded(!signalsExpanded);
                        }}
                        disabled={checkingTrust}
                        aria-expanded={signalsExpanded}
                      >
                        <ShieldCheck size={14} />
                        {checkingTrust
                          ? "Checking source signals…"
                          : signalsExpanded
                          ? "Hide source signals"
                          : `Review source signals ${trust?.evidence?.length ? `(${trust.evidence.length})` : ""}`}
                      </button>
                    </div>

                    {signalsExpanded && (
                      <div className="signals-drawer">
                        {trust?.evidence?.length > 0 ? (
                          <ul className="signals-list">
                            {trust.evidence.map((item, index) => (
                              <li key={`${item.signal}-${index}`} className="signal-item">
                                <div className="signal-badge-row">
                                  <span className="badge badge-warning">{item.signal}</span>
                                  {item.field && <small className="signal-field">Field: {item.field}</small>}
                                </div>
                                {item.quote && <blockquote className="signal-quote">“{item.quote}”</blockquote>}
                                {item.reason && <p className="signal-reason">{item.reason}</p>}
                              </li>
                            ))}
                          </ul>
                        ) : (
                          <div className="signals-empty-state">
                            <CheckCircle2 size={18} style={{ color: "var(--green)", flexShrink: 0 }} />
                            <div>
                              <strong>No risk indicators detected</strong>
                              <p>No rule-based risk indicators were detected in the fields checked.</p>
                            </div>
                          </div>
                        )}
                        <p className="disclaimer" style={{ margin: "6px 0 0", fontSize: "9px", color: "var(--muted)" }}>
                          {trust?.disclaimer || "Risk signals are heuristic and not proof of fraud. Always confirm terms with the original provider."}
                        </p>
                      </div>
                    )}
                  </div>
                </section>
              </article>
              <aside className="detail-aside">
                <div className="apply-card">
                  <h2>Next steps</h2>
                  <p>{opportunity.benefit || "Review the source for application details and benefits."}</p>
                  {opportunity.stipend != null && (
                    <p>
                      <strong>Stipend:</strong> {opportunity.stipend}
                    </p>
                  )}
                  <button
                    type="button"
                    className="button button-primary"
                    onClick={save}
                    disabled={isDemo || saved || saving}
                    aria-describedby="save-status"
                  >
                    {saving ? (
                      <LoaderCircle className="spin" size={16} />
                    ) : saved ? (
                      <BookmarkCheck size={16} />
                    ) : (
                      <BookmarkPlus size={16} />
                    )}
                    {saving
                      ? "Saving…"
                      : saved
                      ? "Saved to applications"
                      : isDemo
                      ? "Sample listing"
                      : "Save opportunity"}
                  </button>
                  <span id="save-status" className="sr-only" aria-live="polite">
                    {notice}
                  </span>
                  {opportunity.application_url && (
                    <a
                      className="button button-secondary external-link"
                      href={opportunity.application_url}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Apply on source site <ArrowUpRight size={14} />
                    </a>
                  )}
                  <div className="side-note">
                    <Sparkles size={16} />
                    <p>
                      Check the original source and eligibility details before sharing documents or paying any fee.
                    </p>
                  </div>
                </div>
              </aside>
            </div>
            {notice && <div className="inline-message" role="status">{notice}</div>}
            {error && <div className="inline-message error" role="alert">{error}</div>}
          </>
        )
      )}
    </ProtectedWorkspace>
  );
}
