"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  FileText,
  ShieldCheck,
  Award,
  Briefcase,
  GraduationCap,
  Sparkles,
  AlertTriangle,
} from "lucide-react";
import ProtectedWorkspace from "@/components/ProtectedWorkspace";
import Loading from "@/components/Loading";
import ResumeUploader from "@/components/ResumeUploader";
import { api } from "@/services/api";
import DemoNotice from "@/components/DemoNotice";
import { demoOpportunities } from "@/utils/demo-data";

export default function ResumePage() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [jobStatus, setJobStatus] = useState("");
  const [analysis, setAnalysis] = useState(null);
  const [documentId, setDocumentId] = useState("");
  const [opportunities, setOpportunities] = useState(demoOpportunities);
  const [selectedOpportunity, setSelectedOpportunity] = useState("");
  const [comparison, setComparison] = useState(null);
  const [comparing, setComparing] = useState(false);
  const [isDemo, setIsDemo] = useState(true);

  useEffect(() => {
    let active = true;
    api
      .opportunities({ limit: 100, offset: 0 })
      .then((result) => {
        if (active) {
          setOpportunities(Array.isArray(result.items) ? result.items : []);
          setIsDemo(false);
        }
      })
      .catch(() => {
        if (active) setIsDemo(true);
      });

    api
      .latestResume()
      .then((saved) => {
        if (!active) return;
        if (saved && !busy) {
          setAnalysis((current) => current || saved);
          setDocumentId((current) => current || saved.document_id || saved.id || "");
        }
      })
      .catch(() => {});

    return () => {
      active = false;
    };
  }, [busy]);

  async function upload(file) {
    setError("");
    setNotice("");
    setAnalysis(null);
    setComparison(null);
    const extension = file.name.split(".").pop()?.toLowerCase();
    if (!["pdf", "docx"].includes(extension)) {
      setError("Only PDF and DOCX files are supported.");
      return;
    }
    setBusy(true);
    setJobStatus("UPLOADING");
    try {
      const response = await api.uploadResume(file);
      const { job_id: jobId, document_id: docId } = response;
      setDocumentId(docId);
      setJobStatus("QUEUED");

      let pollInterval = 1000;
      let completed = false;
      const started = Date.now();
      while (!completed && Date.now() - started < 120000) {
        await new Promise((resolve) => setTimeout(resolve, pollInterval));
        const status = await api.job(jobId);
        setJobStatus(status.status);
        if (status.status === "COMPLETED") {
          completed = true;
          setAnalysis(status.result);
          break;
        }
        if (["FAILED", "DEAD_LETTER"].includes(status.status)) {
          throw new Error("Resume processing could not be completed. Please try again with a simpler file.");
        }
        pollInterval = Math.min(pollInterval * 1.5, 5000);
      }
      if (!completed) throw new Error("Resume processing is taking longer than expected. Please check back shortly.");
      setNotice("Resume analysis is ready. Extracted claims are not automatically written to your profile.");
    } catch (requestError) {
      setError(requestError.message);
      setJobStatus("");
    } finally {
      setBusy(false);
    }
  }

  async function compare() {
    if (!selectedOpportunity || !documentId) return;
    setError("");
    setComparing(true);
    if (isDemo || selectedOpportunity.startsWith("demo-")) {
      setError("Resume comparison requires a live opportunity. Refresh the listings after the opportunity service is available.");
      setComparing(false);
      return;
    }
    try {
      setComparison(await api.matchResume(selectedOpportunity, documentId));
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setComparing(false);
    }
  }

  const skills = analysis?.parsed_skills || analysis?.skills || analysis?.result?.skills || [];
  const readinessScore = typeof analysis?.readiness_score === "number" ? Math.round(analysis.readiness_score) : null;
  const experienceYears = typeof analysis?.experience_years === "number" ? analysis.experience_years : null;
  const education = Array.isArray(analysis?.education) ? analysis.education : [];
  const recommendations = Array.isArray(analysis?.recommendations) ? analysis.recommendations : [];
  const warnings = Array.isArray(analysis?.warnings) ? analysis.warnings : [];
  const selectedOppObj = opportunities.find((item) => item.id === selectedOpportunity) || null;

  return (
    <ProtectedWorkspace>
      <div className="page-heading">
        <div>
          <span className="eyebrow">SKILLS & READINESS</span>
          <h1>Resume analyzer</h1>
          <p>Extract skill claims from a resume and compare them with an opportunity’s requirements.</p>
        </div>
      </div>
      {isDemo && (
        <DemoNotice>
          The sample opportunity options and skill example are previews. Resume comparisons require a live opportunity and are not simulated.
        </DemoNotice>
      )}
      {error && <div className="inline-message error" role="alert">{error}</div>}
      {notice && <div className="inline-message" role="status">{notice}</div>}
      <div className="resume-layout">
        <div>
          <ResumeUploader onUpload={upload} busy={busy} />
          {busy && <Loading label={`Resume ${jobStatus.toLowerCase()}…`} />}

          {analysis && (
            <section className="panel analysis-panel">
              <div className="panel-heading">
                <span className="panel-icon"><FileText size={20} /></span>
                <div>
                  <h2>Resume analysis & credentials</h2>
                  <p>Extracted claims and completeness score based on deterministic analysis.</p>
                </div>
              </div>

              {/* Metrics summary cards */}
              <div className="resume-stats">
                <div className="resume-stat-item">
                  <span className="resume-stat-icon green"><Award size={18} /></span>
                  <div className="resume-stat-info">
                    <strong>{readinessScore !== null ? `${readinessScore}%` : "Pending"}</strong>
                    <span>Readiness score</span>
                  </div>
                </div>
                <div className="resume-stat-item">
                  <span className="resume-stat-icon blue"><Briefcase size={18} /></span>
                  <div className="resume-stat-info">
                    <strong>{experienceYears !== null ? `${experienceYears} yrs` : "0 yrs"}</strong>
                    <span>Estimated exp.</span>
                  </div>
                </div>
                <div className="resume-stat-item">
                  <span className="resume-stat-icon amber"><Sparkles size={18} /></span>
                  <div className="resume-stat-info">
                    <strong>{skills.length}</strong>
                    <span>Skills identified</span>
                  </div>
                </div>
              </div>

              {/* Skills section */}
              <div className="skills-extracted-section">
                <h3 style={{ margin: "0 0 8px", fontSize: "12px", color: "#355340", fontWeight: 800 }}>
                  Extracted technical skills
                </h3>
                {skills.length ? (
                  <div className="skill-tags success-tags">
                    {skills.map((skill) => (
                      <span key={skill}>{skill}</span>
                    ))}
                  </div>
                ) : (
                  <div className="empty-state compact">
                    <h3>No supported skill claims detected</h3>
                    <p>The analyzer uses a limited rule-based vocabulary and may miss relevant skills.</p>
                  </div>
                )}
              </div>

              {/* Education section */}
              {education.length > 0 && (
                <div className="education-section">
                  <h3>Education credentials</h3>
                  <div className="education-cards">
                    {education.map((edu, idx) => (
                      <div key={idx} className="education-card">
                        <GraduationCap size={18} className="edu-icon" />
                        <div>
                          <strong>
                            {edu.degree || "Degree not specified"}
                            {edu.field ? ` · ${edu.field}` : ""}
                          </strong>
                          <p>
                            {edu.institution || "Institution not specified"}
                            {edu.graduation_year ? ` · Class of ${edu.graduation_year}` : ""}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Recommendations */}
              {recommendations.length > 0 && (
                <div className="suggestions-block">
                  <h3>Actionable recommendations</h3>
                  <ul>
                    {recommendations.map((rec, idx) => (
                      <li key={idx}>{rec}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Warnings */}
              {warnings.length > 0 && (
                <div className="resume-warnings">
                  {warnings.map((warn, idx) => (
                    <p key={idx}>
                      <AlertTriangle size={14} /> {warn}
                    </p>
                  ))}
                </div>
              )}

              <p className="disclaimer" style={{ marginTop: "14px" }}>
                {analysis.disclaimer || "Deterministic resume claims and completeness score; not verified qualifications."}
              </p>

              {/* Opportunity Comparison Tool */}
              <div className="resume-compare">
                <label>
                  <span className="field-label">Compare with an opportunity</span>
                  <select
                    className="form-control"
                    value={selectedOpportunity}
                    onChange={(event) => {
                      setSelectedOpportunity(event.target.value);
                      setComparison(null);
                      setError("");
                    }}
                  >
                    <option value="">Choose an opportunity</option>
                    {opportunities.map((item) => (
                      <option value={item.id} key={item.id}>
                        {item.title}
                      </option>
                    ))}
                  </select>
                </label>
                <button
                  className="button button-secondary"
                  type="button"
                  onClick={compare}
                  disabled={!selectedOpportunity || comparing || isDemo || selectedOpportunity.startsWith("demo-")}
                >
                  {comparing ? "Comparing…" : "Compare skills"}
                </button>
              </div>

              {comparison && (
                <div className="match-card">
                  <div className="match-header">
                    <div>
                      <h3>{selectedOppObj?.title || "Opportunity match"}</h3>
                      <p style={{ margin: "2px 0 0", fontSize: "9px", color: "#6e7f73" }}>
                        Skill gap analysis against opportunity requirements
                      </p>
                    </div>
                    {Number.isFinite(comparison.score) && (
                      <span className="match-score-badge">
                        {Math.round(comparison.score)}% match
                      </span>
                    )}
                  </div>
                  <div className="analysis-columns">
                    <div>
                      <h3>Required skills matched</h3>
                      <div className="skill-tags success-tags">
                        {comparison.matched_required?.length ? (
                          comparison.matched_required.map((skill) => <span key={skill}>{skill}</span>)
                        ) : (
                          <p style={{ fontSize: "9px", color: "#8a968d" }}>None identified</p>
                        )}
                      </div>
                    </div>
                    <div>
                      <h3>Required skill gaps</h3>
                      <div className="skill-tags warning-tags">
                        {comparison.missing_required?.length ? (
                          comparison.missing_required.map((skill) => <span key={skill}>{skill}</span>)
                        ) : (
                          <p style={{ fontSize: "9px", color: "#8a968d" }}>No required skill gaps identified</p>
                        )}
                      </div>
                    </div>
                    <div>
                      <h3>Preferred skills to explore</h3>
                      <div className="skill-tags">
                        {comparison.missing_preferred?.length ? (
                          comparison.missing_preferred.map((skill) => <span key={skill}>{skill}</span>)
                        ) : (
                          <p style={{ fontSize: "9px", color: "#8a968d" }}>None identified</p>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </section>
          )}
        </div>

        <aside className="resume-side">
          <div className="panel">
            <span className="panel-icon"><ShieldCheck size={20} /></span>
            <h3>Private by design</h3>
            <div className="benefit-row">
              <span>01</span>
              <div>
                <strong>Supported formats</strong>
                <p>The backend accepts PDF and DOCX files up to 5 MiB.</p>
              </div>
            </div>
            <div className="benefit-row">
              <span>02</span>
              <div>
                <strong>Review before saving</strong>
                <p>Detected claims are not automatically added to your profile.</p>
              </div>
            </div>
            <div className="benefit-row">
              <span>03</span>
              <div>
                <strong>Compare requirements</strong>
                <p>Use skill gaps to plan your preparation. They are not a hiring decision.</p>
              </div>
            </div>
            <Link className="text-link" href="/profile">Update profile skills</Link>
          </div>
          {!analysis && (
            <div className="panel example-analysis">
              <span className="eyebrow">EXAMPLE ONLY</span>
              <h3>What a result can show</h3>
              <p>Illustrative skill claims a student might review:</p>
              <div className="skill-tags">
                <span>Python</span>
                <span>SQL</span>
                <span>Data visualization</span>
              </div>
              <p className="disclaimer">This is not based on an uploaded resume.</p>
            </div>
          )}
        </aside>
      </div>
    </ProtectedWorkspace>
  );
}
