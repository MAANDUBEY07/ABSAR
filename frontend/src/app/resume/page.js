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
  FolderGit2,
  MapPin,
  Mail,
  Phone,
  ExternalLink,
  Target,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  BadgeCheck,
  ArrowUpRight,
  BookOpen,
  Calendar,
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

  // Priority 3: Matches shortlist state
  const [matchingShortlist, setMatchingShortlist] = useState(null);
  const [findingMatches, setFindingMatches] = useState(false);
  const [expandedCategories, setExpandedCategories] = useState({});
  const [showCompletenessBreakdown, setShowCompletenessBreakdown] = useState(false);

  useEffect(() => {
    let active = true;
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
    setMatchingShortlist(null);
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
      setNotice("Resume intelligence ready. Extracted claims are not automatically written to your profile.");
    } catch (requestError) {
      setError(requestError.message);
      setJobStatus("");
    } finally {
      setBusy(false);
    }
  }

  async function findOpportunities() {
    setError("");
    setFindingMatches(true);
    try {
      const matches = await api.matchTopOpportunities(documentId);
      setMatchingShortlist(matches);
    } catch (requestError) {
      setError(requestError.message || "Could not retrieve matching opportunities.");
    } finally {
      setFindingMatches(false);
    }
  }

  const toggleCategory = (cat) => {
    setExpandedCategories((prev) => ({ ...prev, [cat]: !prev[cat] }));
  };

  const candidate = analysis?.candidate || {};
  const experienceEntries = Array.isArray(analysis?.experience) ? analysis.experience : [];
  const skillCategories = analysis?.skill_categories || {};
  const softSkills = Array.isArray(analysis?.soft_skills) ? analysis.soft_skills : [];
  const skills = Array.isArray(analysis?.parsed_skills) && analysis.parsed_skills.length > 0
    ? analysis.parsed_skills
    : (Array.isArray(analysis?.skills) ? analysis.skills : []);
  const technicalSkills = Array.isArray(analysis?.technical_skills) && analysis.technical_skills.length > 0
    ? analysis.technical_skills
    : skills.filter((s) => !softSkills.includes(s));
  const languages = Array.isArray(analysis?.languages) ? analysis.languages : [];
  const projects = Array.isArray(analysis?.projects) ? analysis.projects : [];
  const certifications = Array.isArray(analysis?.certifications) ? analysis.certifications : [];
  const publications = Array.isArray(analysis?.publications) ? analysis.publications : [];
  const completenessScore = typeof analysis?.completeness_score === "number"
    ? Math.round(analysis.completeness_score)
    : (typeof analysis?.readiness_score === "number" ? Math.round(analysis.readiness_score) : null);
  const completenessBreakdown = analysis?.completeness_breakdown || analysis?.readiness_breakdown || null;
  const experienceYears = typeof analysis?.experience_years === "number" ? analysis.experience_years : null;
  const education = Array.isArray(analysis?.education) ? analysis.education : [];
  const recommendations = Array.isArray(analysis?.recommendations) ? analysis.recommendations : [];
  const warnings = Array.isArray(analysis?.warnings) ? analysis.warnings : [];

  return (
    <ProtectedWorkspace>
      <div className="page-heading">
        <div>
          <span className="eyebrow">RESUME INTELLIGENCE</span>
          <h1>Resume analyzer</h1>
          <p>Extract verifiable credentials, analyze documentation completeness, and discover matched opportunities.</p>
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
              {/* Candidate Profile Overview Card */}
              <div className="resume-candidate-card">
                <div className="candidate-name-row">
                  <div>
                    <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
                      <h2>{candidate.name || "Candidate Profile"}</h2>
                      <span style={{ fontSize: "9.5px", background: "var(--surface-soft)", padding: "1px 7px", borderRadius: "10px", color: "var(--muted)", fontWeight: 500, border: "1px solid var(--border)" }}>
                        Extracted from resume
                      </span>
                    </div>
                    {candidate.title && (
                      <span className="candidate-title-badge" style={{ marginTop: "4px", display: "inline-block" }}>
                        {candidate.title}
                      </span>
                    )}
                  </div>
                  {candidate.location && (
                    <span className="candidate-meta-item" style={{ fontWeight: 600 }}>
                      <MapPin size={13} style={{ color: "var(--green)" }} /> {candidate.location}
                    </span>
                  )}
                </div>

                <div className="candidate-meta-row" style={{ marginTop: "8px" }}>
                  {candidate.email && (
                    <span className="candidate-meta-item">
                      <Mail size={12} /> {candidate.email}
                    </span>
                  )}
                  {candidate.phone && (
                    <span className="candidate-meta-item">
                      <Phone size={12} /> {candidate.phone}
                    </span>
                  )}
                  {candidate.linkedin && (
                    <span className="candidate-meta-item">
                      <ExternalLink size={12} />
                      <a href={`https://${candidate.linkedin.replace(/^https?:\/\//, "")}`} target="_blank" rel="noopener noreferrer">
                        LinkedIn
                      </a>
                    </span>
                  )}
                  {candidate.github && (
                    <span className="candidate-meta-item">
                      <ExternalLink size={12} />
                      <a href={`https://${candidate.github.replace(/^https?:\/\//, "")}`} target="_blank" rel="noopener noreferrer">
                        GitHub
                      </a>
                    </span>
                  )}
                </div>
              </div>

              {/* Metrics summary cards */}
              <div className="resume-stats">
                <div
                  className="resume-stat-item"
                  style={{ cursor: "pointer" }}
                  onClick={() => setShowCompletenessBreakdown(!showCompletenessBreakdown)}
                  title="Click to view breakdown"
                >
                  <span className="resume-stat-icon green"><Award size={18} /></span>
                  <div className="resume-stat-info">
                    <strong>{completenessScore !== null ? `${completenessScore}%` : "Pending"}</strong>
                    <span>Completeness score {showCompletenessBreakdown ? "▲" : "▼"}</span>
                  </div>
                </div>
                <div className="resume-stat-item">
                  <span className="resume-stat-icon blue"><Briefcase size={18} /></span>
                  <div className="resume-stat-info">
                    <strong>{experienceYears !== null ? `${experienceYears} yrs` : "0 yrs"}</strong>
                    <span>Completed experience</span>
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

              {/* Completeness Score Breakdown */}
              {showCompletenessBreakdown && completenessBreakdown && (
                <div className="readiness-breakdown-box" style={{ margin: "10px 0 16px", padding: "14px", background: "var(--surface-soft)", borderRadius: "10px", border: "1px solid var(--line)" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                    <span style={{ fontSize: "11px", fontWeight: 800, color: "var(--ink)", textTransform: "uppercase", letterSpacing: "0.5px" }}>
                      Profile Completeness Breakdown
                    </span>
                    <span style={{ fontSize: "12px", fontWeight: 800, color: "var(--green)" }}>
                      {completenessBreakdown.total_score || completenessScore}% Total
                    </span>
                  </div>
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))", gap: "8px", fontSize: "10px", color: "var(--muted)" }}>
                    <div>Contact: <strong>{completenessBreakdown.contact_score}/10</strong></div>
                    <div>Education: <strong>{completenessBreakdown.education_score}/25</strong></div>
                    <div>Experience: <strong>{completenessBreakdown.experience_score}/25</strong></div>
                    <div>Technical skills: <strong>{completenessBreakdown.technical_skills_score}/20</strong></div>
                    <div>Soft skills & credentials: <strong>{completenessBreakdown.soft_skills_and_languages_score}/20</strong></div>
                  </div>
                  <p style={{ margin: "8px 0 0", fontSize: "9.5px", color: "var(--muted)", lineHeight: 1.4, fontStyle: "italic" }}>
                    Note: Completeness score measures documentation coverage of resume sections, not job-readiness or hiring guarantees.
                  </p>
                </div>
              )}

              {/* Professional Experience Timeline */}
              {experienceEntries.length > 0 && (
                <div className="section-block">
                  <div className="section-block-header">
                    <h3><Briefcase size={14} style={{ color: "var(--green)" }} /> Professional experience ({experienceEntries.length})</h3>
                  </div>
                  <div className="experience-timeline">
                    {experienceEntries.map((exp, idx) => (
                      <div key={idx} className="timeline-card">
                        <div className="timeline-header">
                          <div className="timeline-role-info">
                            <strong>{exp.title}</strong>
                            <span>{exp.organization}{exp.location ? ` · ${exp.location}` : ""}</span>
                          </div>
                          <div className="timeline-badges">
                            {exp.is_current && <span className="current-pill">Current role</span>}
                            <span className="duration-pill"><Calendar size={11} style={{ marginRight: 3, verticalAlign: -1 }} />{exp.duration || `${exp.start_date} – ${exp.end_date}`}</span>
                          </div>
                        </div>

                        {exp.responsibilities?.length > 0 && (
                          <ul className="timeline-resp-list">
                            {exp.responsibilities.map((resp, rIdx) => (
                              <li key={rIdx}>{resp}</li>
                            ))}
                          </ul>
                        )}

                        {exp.achievements?.length > 0 && (
                          <div className="achievement-list">
                            {exp.achievements.map((ach, aIdx) => (
                              <div key={aIdx} className="achievement-tag">
                                <Target size={12} style={{ color: "var(--green)", flexShrink: 0, marginTop: 2 }} />
                                <span><strong>Key achievement:</strong> {ach}</span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Categorized Technical Skills */}
              <div className="section-block">
                <div className="section-block-header">
                  <h3><Sparkles size={14} style={{ color: "var(--green)" }} /> Technical skills ({technicalSkills.length})</h3>
                </div>

                {Object.keys(skillCategories).length > 0 ? (
                  <div className="skill-categories-grid">
                    {Object.entries(skillCategories)
                      .filter(([cat]) => cat !== "Soft Skills & Professional Competencies")
                      .map(([catName, catSkills]) => {
                        const isExpanded = expandedCategories[catName];
                        const displayedSkills = isExpanded ? catSkills : catSkills.slice(0, 8);
                        const hasMore = catSkills.length > 8;

                        return (
                          <div key={catName} className="skill-category-card">
                            <div className="skill-category-title">
                              <span>{catName}</span>
                              <span style={{ fontSize: "9.5px", color: "var(--muted)", fontWeight: 600 }}>
                                {catSkills.length} skill{catSkills.length === 1 ? "" : "s"}
                              </span>
                            </div>
                            <div className="skill-chips-row">
                              {displayedSkills.map((skill) => (
                                <span key={skill} className="skill-chip required">
                                  {skill}
                                </span>
                              ))}
                            </div>
                            {hasMore && (
                              <button
                                type="button"
                                className="show-all-btn"
                                onClick={() => toggleCategory(catName)}
                              >
                                {isExpanded ? "Show fewer" : `Show all (${catSkills.length})`}
                              </button>
                            )}
                          </div>
                        );
                      })}
                  </div>
                ) : technicalSkills.length > 0 ? (
                  <div className="skill-chips-row">
                    {technicalSkills.map((skill) => (
                      <span key={skill} className="skill-chip required">
                        {skill}
                      </span>
                    ))}
                  </div>
                ) : (
                  <p style={{ margin: 0, fontSize: "10px", color: "var(--muted)", fontStyle: "italic" }}>
                    No technical domain tools or programming languages detected on this resume.
                  </p>
                )}
              </div>

              {/* Soft Skills & Professional Competencies */}
              <div className="section-block">
                <div className="section-block-header">
                  <h3><Award size={14} style={{ color: "var(--orange)" }} /> Soft skills & professional competencies ({softSkills.length})</h3>
                </div>
                {softSkills.length > 0 ? (
                  <div className="skill-chips-row">
                    {softSkills.map((skill) => (
                      <span key={skill} className="skill-chip preferred">
                        {skill}
                      </span>
                    ))}
                  </div>
                ) : (
                  <p style={{ margin: 0, fontSize: "10px", color: "var(--muted)", fontStyle: "italic" }}>
                    No professional competency claims detected.
                  </p>
                )}
              </div>

              {/* Education Credentials */}
              <div className="section-block">
                <div className="section-block-header">
                  <h3><GraduationCap size={14} style={{ color: "var(--green)" }} /> Education credentials ({education.length})</h3>
                </div>
                {education.length > 0 ? (
                  <div className="credentials-double-grid">
                    {education.map((item, index) => (
                      <div className="credential-card" key={index}>
                        <strong>
                          {item.degree || "Degree"} {item.field ? `· ${item.field}` : ""}
                        </strong>
                        <p>{item.institution || "Institution name unconfirmed"}</p>
                        <p style={{ display: "flex", justifyContent: "space-between", marginTop: "4px", fontSize: "9.5px" }}>
                          <span>Class of {item.graduation_year || "N/A"}</span>
                          {item.gpa && <span style={{ fontWeight: 700, color: "var(--green)" }}>GPA: {item.gpa}</span>}
                        </p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p style={{ margin: 0, fontSize: "10px", color: "var(--muted)", fontStyle: "italic" }}>
                    No formal degree entries identified.
                  </p>
                )}
              </div>

              {/* Selected Projects */}
              {projects.length > 0 && (
                <div className="section-block">
                  <div className="section-block-header">
                    <h3><FolderGit2 size={14} style={{ color: "var(--green)" }} /> Selected projects ({projects.length})</h3>
                  </div>
                  <div className="projects-grid">
                    {projects.map((proj, idx) => (
                      <div key={idx} className="project-card">
                        <div className="project-card-header">
                          <strong>{proj.name}</strong>
                          {proj.technologies?.length > 0 && (
                            <div className="skill-chips-row">
                              {proj.technologies.map((t) => (
                                <span key={t} className="skill-chip" style={{ background: "var(--surface-soft)", fontSize: "9px" }}>
                                  {t}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                        {proj.description && <p className="project-description">{proj.description}</p>}
                        {proj.outcomes?.length > 0 && (
                          <div style={{ marginTop: "4px" }}>
                            {proj.outcomes.map((out, oIdx) => (
                              <div key={oIdx} className="project-outcome-pill">
                                <Target size={11} style={{ flexShrink: 0, marginTop: 1 }} />
                                <span><strong>Outcome:</strong> {out}</span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Additional Credentials: Certifications, Publications, Languages */}
              {(certifications.length > 0 || publications.length > 0 || languages.length > 0) && (
                <div className="section-block">
                  <div className="section-block-header">
                    <h3><BadgeCheck size={14} style={{ color: "var(--green)" }} /> Additional credentials</h3>
                  </div>
                  <div className="credentials-double-grid">
                    {certifications.map((cert, idx) => (
                      <div key={`cert-${idx}`} className="credential-card">
                        <strong><BadgeCheck size={12} style={{ color: "var(--green)", marginRight: 4, verticalAlign: -1 }} /> {cert.name}</strong>
                        <p>{cert.issuer ? `Issuer: ${cert.issuer}` : "Verified credential"} {cert.year ? `(${cert.year})` : ""}</p>
                      </div>
                    ))}
                    {publications.map((pub, idx) => (
                      <div key={`pub-${idx}`} className="credential-card">
                        <strong><BookOpen size={12} style={{ color: "var(--green)", marginRight: 4, verticalAlign: -1 }} /> “{pub.title}”</strong>
                        <p>{pub.venue || "Academic Publication"} {pub.year ? `(${pub.year})` : ""}</p>
                      </div>
                    ))}
                    {languages.map((lang, idx) => (
                      <div key={`lang-${idx}`} className="credential-card">
                        <strong><Languages size={12} style={{ color: "var(--green)", marginRight: 4, verticalAlign: -1 }} /> {lang.language}</strong>
                        <p>Proficiency: <span style={{ fontWeight: 700, color: "var(--green)" }}>{lang.proficiency}</span></p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Recommendations & Warnings */}
              {recommendations.length > 0 && (
                <div className="section-block">
                  <div className="section-block-header">
                    <h3>Specific recommendations for improvement</h3>
                  </div>
                  <ul className="criteria-items" style={{ margin: 0 }}>
                    {recommendations.map((rec, idx) => (
                      <li key={idx} className="criteria-item">
                        <strong>Action:</strong> {rec}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {warnings.length > 0 && (
                <div className="resume-warnings" style={{ marginTop: "16px" }}>
                  {warnings.map((warn, index) => (
                    <p key={index}>
                      <AlertTriangle size={13} style={{ flexShrink: 0 }} /> {warn}
                    </p>
                  ))}
                </div>
              )}

              <p className="disclaimer" style={{ marginTop: "14px" }}>
                {analysis?.disclaimer || "Deterministic resume claims and completeness score; confirm explicitly through profile updates"}
              </p>

              {/* Priority 3: Find Opportunities Matching My Resume */}
              <div className="matches-section">
                <div className="matches-hero">
                  <div>
                    <h3><Sparkles size={16} style={{ color: "var(--green)" }} /> Find opportunities matching my resume</h3>
                    <p style={{ margin: "2px 0 0", fontSize: "10.5px", color: "var(--muted)" }}>
                      Ranks the 3 strongest opportunity matches based on actual measurable requirements and extracted skills.
                    </p>
                  </div>
                  <button
                    type="button"
                    className="button button-primary"
                    onClick={findOpportunities}
                    disabled={findingMatches}
                  >
                    {findingMatches ? "Evaluating matches…" : "Find matching opportunities"}
                  </button>
                </div>

                {matchingShortlist && (
                  <div className="matches-cards-grid">
                    {matchingShortlist.length > 0 ? (
                      matchingShortlist.map((opp) => (
                        <div key={opp.opportunity_id} className="matched-opp-card">
                          <div className="matched-opp-header">
                            <div className="matched-opp-title">
                              <strong>{opp.title}</strong>
                              <span>{opp.organization} · {opp.location}</span>
                            </div>
                            {opp.criteria_available && opp.match_percentage !== null ? (
                              <span className="match-score-badge measurable">
                                {opp.match_percentage}% match
                              </span>
                            ) : (
                              <span className="match-score-badge unscored">
                                Unscored (requirements unstated)
                              </span>
                            )}
                          </div>

                          <div className="match-skills-block">
                            {opp.matched_skills?.length > 0 && (
                              <div>
                                <span className="label">Matched skills: </span>
                                <span style={{ color: "var(--green-dark)", fontWeight: 700 }}>
                                  {opp.matched_skills.join(", ")}
                                </span>
                              </div>
                            )}

                            {opp.missing_skills?.length > 0 && (
                              <div style={{ marginTop: 2 }}>
                                <span className="label">Missing skills: </span>
                                <span style={{ color: "#9a6c2c", fontWeight: 600 }}>
                                  {opp.missing_skills.join(", ")}
                                </span>
                              </div>
                            )}

                            {opp.reasons?.length > 0 && (
                              <ul className="match-reasons-list">
                                {opp.reasons.map((r, rIdx) => (
                                  <li key={rIdx}>• {r}</li>
                                ))}
                              </ul>
                            )}
                          </div>

                          <div className="match-action-row">
                            <Link href={opp.detail_url || `/opportunities/${opp.opportunity_id}`} className="view-opp-button">
                              <span>View opportunity details</span>
                              <ArrowUpRight size={13} />
                            </Link>
                          </div>
                        </div>
                      ))
                    ) : (
                      <p style={{ margin: 0, fontSize: "10px", color: "var(--muted)", fontStyle: "italic" }}>
                        No opportunity matches found for the current skills profile.
                      </p>
                    )}
                  </div>
                )}
              </div>
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
                <strong>Meaningful matching</strong>
                <p>Opportunities are scored exclusively on measurable requirements, never arbitrary claims.</p>
              </div>
            </div>
            <Link className="text-link" href="/profile">Update profile skills</Link>
          </div>
          {!analysis && (
            <div className="panel example-analysis">
              <span className="eyebrow">RESUME INTELLIGENCE</span>
              <h3>What is extracted</h3>
              <p>Uploaded CVs are processed for:</p>
              <div className="skill-tags">
                <span>Experience Timeline</span>
                <span>Technical Skills</span>
                <span>Soft Skills</span>
                <span>Projects & Outcomes</span>
                <span>Certifications</span>
                <span>Publications</span>
              </div>
              <p className="disclaimer">Rule-based deterministic extraction ensures data accuracy without AI hallucinations.</p>
            </div>
          )}
        </aside>
      </div>
    </ProtectedWorkspace>
  );
}
