"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { FileText, ShieldCheck } from "lucide-react";
import ProtectedWorkspace from "@/components/ProtectedWorkspace";
import ResumeUploader from "@/components/ResumeUploader";
import Loading from "@/components/Loading";
import { api } from "@/services/api";

const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

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
        if (active) setOpportunities(Array.isArray(result.items) ? result.items : []);
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
    setError(""); setNotice(""); setAnalysis(null); setComparison(null);
    const extension = file.name.split(".").pop()?.toLowerCase();
    if (!new Set(["pdf", "docx"]).has(extension)) { setError("Choose a PDF or DOCX resume."); return; }
    if (file.size === 0 || file.size > 5 * 1024 * 1024) { setError("The file must be non-empty and no larger than 5 MiB."); return; }
    setBusy(true); setJobStatus("Uploading");
    try {
      const accepted = await api.uploadResume(file);
      setDocumentId(accepted.document_id);
      let job = null;
      for (let attempt = 0; attempt < 30; attempt += 1) {
        setJobStatus(attempt === 0 ? "Processing" : `Processing (${attempt * 2}s)`);
        job = await api.jobResult(accepted.job_id);
        if (job.status === "COMPLETED") break;
        if (["DEAD_LETTER", "CANCELLED"].includes(job.status)) throw new Error("Resume analysis did not complete. Please try another supported file.");
        await wait(2000);
      }
      if (job?.status !== "COMPLETED") throw new Error("Resume analysis is taking longer than expected. Check back in a moment and upload again only if the result does not appear.");
      const result = job.result;
      if (!result) throw new Error("The job completed, but no resume analysis was returned.");
      setAnalysis(result);
      setJobStatus("Completed");
      setNotice("Resume analysis is ready. Extracted claims are not automatically written to your profile.");
    } catch (requestError) { setError(requestError.message); setJobStatus(""); }
    finally { setBusy(false); }
  }

  async function compare() {
    if (!selectedOpportunity || !documentId) return;
    setError(""); setComparing(true);
    try { setComparison(await api.matchResume(selectedOpportunity, documentId)); }
    catch (requestError) { setError(requestError.message); }
    finally { setComparing(false); }
  }

  const skills = analysis?.skills || analysis?.result?.skills || [];
  return <ProtectedWorkspace>
    <div className="page-heading"><div><span className="eyebrow">SKILLS & READINESS</span><h1>Resume analyzer</h1><p>Extract skill claims from a resume and compare them with an opportunity’s requirements.</p></div></div>
    {error && <div className="inline-message error" role="alert">{error}</div>}
    {notice && <div className="inline-message" role="status">{notice}</div>}
    <div className="resume-layout">
      <div>
        <ResumeUploader onUpload={upload} busy={busy} />
        {busy && <Loading label={`Resume ${jobStatus.toLowerCase()}…`} />}
        {analysis && <section className="panel"><h2>Deterministic resume analysis</h2><p>Readiness (rule-based): {analysis.readiness_score ?? "Unavailable"}</p><p>Experience estimate: {analysis.experience_years ?? "Unknown"} years</p><pre>{JSON.stringify(analysis.education || [], null, 2)}</pre><ul>{(analysis.recommendations || []).map((item) => <li key={item}>{item}</li>)}</ul>{(analysis.warnings || []).map((item) => <p key={item}>{item}</p>)}</section>}
        {analysis && <section className="panel analysis-panel"><div className="panel-heading"><span className="panel-icon"><FileText size={20} /></span><div><h2>Extracted skill claims</h2><p>Review these claims before adding them to your profile.</p></div></div>{skills.length ? <div className="skill-tags success-tags">{skills.map((skill) => <span key={skill}>{skill}</span>)}</div> : <div className="empty-state compact"><h3>No supported skill claims detected</h3><p>The analyzer uses a limited rule-based vocabulary and may miss relevant skills.</p></div>}<p className="disclaimer">{analysis.disclaimer || "Resume extraction is not a verification of skills or experience."}</p>
          <div className="resume-compare"><label><span className="field-label">Compare with an opportunity</span><select className="form-control" value={selectedOpportunity} onChange={(event) => setSelectedOpportunity(event.target.value)}><option value="">Choose an opportunity</option>{opportunities.map((item) => <option value={item.id} key={item.id}>{item.title}</option>)}</select></label><button className="button button-secondary" type="button" onClick={compare} disabled={!selectedOpportunity || comparing}>{comparing ? "Comparing…" : "Compare skills"}</button></div>
          {comparison && <div className="analysis-columns"><div><h3>Required skills matched</h3><div className="skill-tags success-tags">{comparison.matched_required?.length ? comparison.matched_required.map((skill) => <span key={skill}>{skill}</span>) : <p>None identified</p>}</div></div><div><h3>Required skill gaps</h3><div className="skill-tags warning-tags">{comparison.missing_required?.length ? comparison.missing_required.map((skill) => <span key={skill}>{skill}</span>) : <p>No required skill gaps identified</p>}</div></div><div><h3>Preferred skills to explore</h3><div className="skill-tags">{comparison.missing_preferred?.length ? comparison.missing_preferred.map((skill) => <span key={skill}>{skill}</span>) : <p>None identified</p>}</div></div>{Number.isFinite(comparison.score) && <p>Required skill match: {Math.round(comparison.score)}%</p>}</div>}
        </section>}
      </div>
      <aside className="resume-side"><div className="panel"><span className="panel-icon"><ShieldCheck size={20} /></span><h3>Private by design</h3><div className="benefit-row"><span>01</span><div><strong>Supported formats</strong><p>The backend accepts PDF and DOCX files up to 5 MiB.</p></div></div><div className="benefit-row"><span>02</span><div><strong>Review before saving</strong><p>Detected claims are not automatically added to your profile.</p></div></div><div className="benefit-row"><span>03</span><div><strong>Compare requirements</strong><p>Use skill gaps to plan your preparation. They are not a hiring decision.</p></div></div><Link className="text-link" href="/profile">Update profile skills</Link></div></aside>
    </div>
  </ProtectedWorkspace>;
}
