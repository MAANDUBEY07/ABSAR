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
  Languages,
} from "lucide-react";
import ProtectedWorkspace from "@/components/ProtectedWorkspace";
import Loading from "@/components/Loading";
import ResumeUploader from "@/components/ResumeUploader";
import { api } from "@/services/api";

export default function ResumePage() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [jobStatus, setJobStatus] = useState("");
  const [analysis, setAnalysis] = useState(null);
  const [documentId, setDocumentId] = useState("");
  const [opportunities, setOpportunities] = useState([]);
  const [selectedOpportunity, setSelectedOpportunity] = useState("");
  const [comparison, setComparison] = useState(null);
  const [comparing, setComparing] = useState(false);

  useEffect(() => {
    let active = true;
    api
      .opportunities({ limit: 100, offset: 0 })
      .then((result) => {
        if (active) {
          setOpportunities(Array.isArray(result.items) ? result.items : []);
        }
      })
      .catch(() => {});

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
    if (selectedOpportunity.startsWith("demo-")) {
      setError("Resume comparison requires a live opportunity.");
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
  const technicalSkills = Array.isArray(analysis?.technical_skills) ? analysis.technical_skills : [];
  const softSkills = Array.isArray(analysis?.soft_skills) ? analysis.soft_skills : [];
  const languages = Array.isArray(analysis?.languages) ? analysis.languages : [];
  const readinessScore = typeof analysis?.readiness_score === "number" ? Math.round(analysis.readiness_score) : null;
  const readinessBreakdown = analysis?.readiness_breakdown || null;
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

              {/* Readiness Breakdown */}
              {readinessBreakdown && (
                <div className="readiness-breakdown-box" style={{ margin: "14px 0", padding: "12px", background: "#f8faf9", borderRadius: "8px", border: "1px solid #e1e8e4" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                    <span style={{ fontSize: "11px", fontWeight: 700, color: "#2d4d38", textTransform: "uppercase", letterSpacing: "0.5px" }}>
                      Profile Completeness Breakdown
                    </span>
                    <span style={{ fontSize: "12px", fontWeight: 800, color: "#166534" }}>
                      {readinessScore}%
                    </span>
                  </div>
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))", gap: "8px", fontSize: "10px", color: "#4b5563" }}>
                    <div>Contact details: <strong>{readinessBreakdown.contact_score ?? 0} / 10</strong></div>
                    <div>Education credentials: <strong>{readinessBreakdown.education_score ?? 0} / 25</strong></div>
                    <div>Experience history: <strong>{readinessBreakdown.experience_score ?? 0} / 25</strong></div>
                    <div>Technical skills: <strong>{readinessBreakdown.technical_skills_score ?? 0} / 20</strong></div>
                    <div>Soft skills & languages: <strong>{readinessBreakdown.soft_skills_and_languages_score ?? 0} / 20</strong></div>
                  </div>
                  {readinessBreakdown.explanation && (
                    <p style={{ margin: "8px 0 0", fontSize: "9px", color: "#6b7280", lineHeight: 1.4 }}>
                      {readinessBreakdown.explanation}
                    </p>
                  )}
                </div>
              )}

              {/* Technical Skills section */}
              <div className="skills-extracted-section">
                <h3 style={{ margin: "0 0 8px", fontSize: "12px", color: "#355340", fontWeight: 800 }}>
                  Extracted technical skills
                </h3>
                {technicalSkills.length ? (
                  <div className="skill-tags success-tags">
                    {technicalSkills.map((skill) => (
                      <span key={skill}>{skill}</span>
                    ))}
                  </div>
                ) : (
                  <div className="empty-state compact" style={{ padding: "8px 12px" }}>
                    <p style={{ margin: 0, fontSize: "10px", color: "#6b7280" }}>
                      No technical domain tools or programming languages detected on this resume.
                    </p>
                  </div>
                )}
              </div>

              {/* Soft Skills section */}
              <div className="skills-extracted-section" style={{ marginTop: "12px" }}>
                <h3 style={{ margin: "0 0 8px", fontSize: "12px", color: "#355340", fontWeight: 800 }}>
                  Soft skills & professional competencies
                </h3>
                {softSkills.length ? (
                  <div className="skill-tags success-tags">
                    {softSkills.map((skill) => (
                      <span key={skill}>{skill}</span>
                    ))}
                  </div>
                ) : (
                  <div className="empty-state compact" style={{ padding: "8px 12px" }}>
                    <p style={{ margin: 0, fontSize: "10px", color: "#6b7280" }}>
                      No professional competency claims detected.
                    </p>
                  </div>
                )}
              </div>

              {/* Languages section */}
              {languages.length > 0 && (
                <div className="languages-extracted-section" style={{ marginTop: "12px" }}>
                  <h3 style={{ margin: "0 0 8px", fontSize: "12px", color: "#355340", fontWeight: 800, display: "flex", alignItems: "center", gap: "6px" }}>
                    <Languages size={14} /> Languages & proficiencies
                  </h3>
                  <div className="skill-tags">
                    {languages.map((item, idx) => (
                      <span key={idx} style={{ background: "#edf5f0", color: "#22593b", borderColor: "#c4e2cd" }}>
                        <strong>{item.language}</strong> · {item.proficiency}
                      </span>
                    ))}
                  </div>
                </div>
              )}

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
                            {edu.gpa ? ` · GPA: ${edu.gpa}` : ""}
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
                  disabled={!selectedOpportunity || comparing || selectedOpportunity.startsWith("demo-")}
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

                  {comparison.criteria_available === false ? (
                    <div className="empty-state compact" style={{ marginTop: "12px", padding: "10px 12px" }}>
                      <p style={{ margin: 0, fontSize: "10px", color: "#6e7f73" }}>
                        Skill criteria unavailable for this opportunity: The source listing did not specify required or preferred skills.
                      </p>
                    </div>
                  ) : (
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
                  )}
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
