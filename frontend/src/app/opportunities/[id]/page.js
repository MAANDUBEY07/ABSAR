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
  LoaderCircle,
  MapPin,
  RefreshCw,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import ProtectedWorkspace from "@/components/ProtectedWorkspace";
import Loading from "@/components/Loading";
import EligibilityBadge from "@/components/EligibilityBadge";
import TrustBadge from "@/components/TrustBadge";
import { api } from "@/services/api";
import { CATEGORY_LABELS } from "@/utils/constants";
import DemoNotice from "@/components/DemoNotice";
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
      setOpportunity(await api.opportunity(id));
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

  async function checkEligibility() {
    setChecking(true);
    setError("");
    if (isDemo) {
      setError("Eligibility checks are unavailable for sample listings. Open a live listing to check eligibility.");
      setChecking(false);
      return;
    }
    try {
      setEligibility(await api.eligibility(id));
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

  return (
    <ProtectedWorkspace>
      <Link className="back-link" href="/opportunities">
        ← Back to opportunities
      </Link>
      {isDemo && opportunity && (
        <DemoNotice>
          This fictional listing is display-only. Saving, eligibility checks and source checks require a live listing.
        </DemoNotice>
      )}
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
                    {opportunity.remote === true
                      ? "Online"
                      : opportunity.remote === false
                      ? "On-site"
                      : "Mode not specified"}
                  </span>
                </div>
                <section className="detail-section">
                  <h2>About this opportunity</h2>
                  <p className="preserve-lines">
                    {opportunity.description || "No description has been provided."}
                  </p>
                </section>
                <section className="detail-section">
                  <h2>Eligibility requirements</h2>
                  {opportunity.requirements?.confirmed ? (
                    <ul className="reason-list">
                      {opportunity.requirements.graduation_years?.length > 0 && (
                        <li>Graduation year: {opportunity.requirements.graduation_years.join(", ")}</li>
                      )}
                      {opportunity.requirements.degrees?.length > 0 && (
                        <li>Degree: {opportunity.requirements.degrees.join(", ")}</li>
                      )}
                      {opportunity.requirements.branches?.length > 0 && (
                        <li>Branch: {opportunity.requirements.branches.join(", ")}</li>
                      )}
                      {opportunity.requirements.min_cgpa != null && (
                        <li>Minimum CGPA: {opportunity.requirements.min_cgpa}</li>
                      )}
                      {opportunity.requirements.locations?.length > 0 && (
                        <li>Location: {opportunity.requirements.locations.join(", ")}</li>
                      )}
                      {opportunity.requirements.required_skills?.length > 0 && (
                        <li>Required skills: {opportunity.requirements.required_skills.join(", ")}</li>
                      )}
                      {opportunity.requirements.preferred_skills?.length > 0 && (
                        <li>Preferred skills: {opportunity.requirements.preferred_skills.join(", ")}</li>
                      )}
                    </ul>
                  ) : (
                    <p>Eligibility criteria have not been confirmed by the source.</p>
                  )}
                  <button
                    className="button button-secondary"
                    type="button"
                    onClick={checkEligibility}
                    disabled={checking}
                  >
                    {checking ? "Checking…" : "Check my eligibility"}
                  </button>

                  {eligibility && (
                    <div className="eligibility-result">
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
                          <span style={{ fontSize: "10px", fontWeight: 800, color: "#326e47" }}>
                            Criteria coverage: {Math.round(eligibility.score)}%
                          </span>
                        )}
                      </div>

                      <p
                        style={{
                          margin: "4px 0 8px",
                          fontSize: "10px",
                          color: "#375543",
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
                            The source has not published or confirmed specific eligibility criteria. AVSAR cannot verify your eligibility without confirmed rules.
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
                <section className="detail-section">
                  <h2>Source and verification</h2>
                  <div className="source-details">
                    <span>Source status</span>
                    <TrustBadge
                      status={opportunity.verification_status}
                      report={trust}
                    />
                    {opportunity.source_url && (
                      <a href={opportunity.source_url} target="_blank" rel="noreferrer">
                        Open original source <ArrowUpRight size={13} />
                      </a>
                    )}
                  </div>
                  <button
                    className="button button-secondary"
                    type="button"
                    onClick={checkTrust}
                    disabled={checkingTrust}
                  >
                    <ShieldCheck size={15} />
                    {checkingTrust ? "Checking source signals…" : "Review source signals"}
                  </button>
                  {trust && (
                    <div className="trust-report">
                      <p>
                        <strong>Risk signals: {trust.risk_level || "Not assessed"}</strong>
                        {Number.isFinite(trust.risk_score) && <> · score {trust.risk_score}/100</>}
                      </p>
                      <p>Verification status: {trust.verification_status || "Unknown"}</p>
                      {trust.evidence?.length > 0 ? (
                        <ul className="reason-list">
                          {trust.evidence.map((item, index) => (
                            <li key={`${item.signal}-${index}`}>
                              <strong>{item.signal}</strong>
                              {item.quote ? ` — “${item.quote}”` : ""}
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p>No rule-based risk signals were found in the checked fields.</p>
                      )}
                      <p className="disclaimer">
                        {trust.disclaimer ||
                          "Risk signals are not a verified fraud classification. Confirm details with the original source."}
                      </p>
                    </div>
                  )}
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
