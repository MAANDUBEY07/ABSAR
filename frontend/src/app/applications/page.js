"use client";

import { useCallback, useEffect, useState, useRef } from "react";
import Link from "next/link";
import { ArrowUpRight, ClipboardList, RefreshCw } from "lucide-react";
import ProtectedWorkspace from "@/components/ProtectedWorkspace";
import Loading from "@/components/Loading";
import { api } from "@/services/api";
import { APPLICATION_STATUS_LABELS, BACKEND_APPLICATION_TRANSITIONS } from "@/utils/constants";

const transitionLabel = {
  DRAFT: "PREPARING",
  READY_FOR_REVIEW: "PREPARING Â· ready for review",
  ASSESSMENT: "APPLIED Â· assessment",
  INTERVIEW: "SHORTLISTED Â· interview",
  OFFER: "SELECTED Â· offer",
  REJECTED: "REJECTED",
};

export default function ApplicationsPage() {
  const submissionKeys = useRef({});
  const [materials, setMaterials] = useState({});
  const [confirmations, setConfirmations] = useState({});
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [updating, setUpdating] = useState("");
  const [itemErrors, setItemErrors] = useState({});
  const load = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const applications = await api.applications({ limit: 100, offset: 0 });
      const rows = await Promise.all((Array.isArray(applications) ? applications : []).map(async (application) => {
        try { return { ...application, opportunity: await api.opportunity(application.opportunity_id) }; }
        catch { return { ...application, opportunity: null }; }
      }));
      setItems(rows);
    } catch (requestError) { setError(requestError.message); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  async function updateStatus(application, nextStatus) {
    if (nextStatus === "DRAFT") { setConfirmations((current) => ({ ...current, [application.id]: false })); delete submissionKeys.current[application.id]; }
    setUpdating(application.id); setNotice(""); setItemErrors((current) => ({ ...current, [application.id]: "" }));
    try {
      const updated = await api.updateApplication(application.id, application.revision, nextStatus);
      setItems((current) => current.map((item) => item.id === application.id ? { ...item, ...updated } : item));
      setNotice("Application status updated.");
    } catch (requestError) {
      setItemErrors((current) => ({ ...current, [application.id]: requestError.message }));
      if (requestError.status === 409) await load();
    } finally { setUpdating(""); }
  }

  async function act(application, action) {
    setUpdating(application.id); setItemErrors((current) => ({ ...current, [application.id]: "" }));
    try {
      let updated;
      if (action === "save") {
        updated = await api.updateApplicationMaterial(application.id, application.revision, { ...application.material, statement: materials[application.id] ?? application.material?.statement ?? "" });
      } else if (action === "approve") {
        updated = await api.approveApplication(application.id, application.revision);
      } else {
        if (!confirmations[application.id]) throw new Error("Confirm submission before continuing.");
        const storageKey = `avsar:submission:${application.id}:${application.revision}`;
        const key = submissionKeys.current[application.id] || sessionStorage.getItem(storageKey) || crypto.randomUUID();
        submissionKeys.current[application.id] = key;
        sessionStorage.setItem(storageKey, key);
        const receipt = await api.submitApplication(application.id, application.revision, key);
        setNotice(`Submission recorded: ${receipt.application_id}. External delivery is not verified.`);
        await load();
        return;
      }
      setItems((current) => current.map((item) => item.id === application.id ? { ...item, ...updated } : item));
      setNotice(action === "approve" ? "Materials explicitly approved. Confirm submission separately." : "Materials saved; review before approval.");
    } catch (requestError) {
      setItemErrors((current) => ({ ...current, [application.id]: requestError.message }));
      if (requestError.status === 409) await load();
    } finally { setUpdating(""); }
  }

  return <ProtectedWorkspace>
    <div className="page-heading"><div><span className="eyebrow">YOUR PROGRESS</span><h1>My applications</h1><p>Track saved opportunities and update statuses supported by the current application API.</p></div><button className="button button-secondary" type="button" onClick={load} disabled={loading}><RefreshCw size={15} /> Refresh</button></div>
    {error && <div className="inline-message error" role="alert">{error}</div>}
    {notice && <div className="inline-message" role="status">{notice}</div>}
    {loading ? <Loading label="Loading your applications" /> : items.length ? <div className="tracker-list">{items.map((application) => {
      const transitions = BACKEND_APPLICATION_TRANSITIONS[application.status] || [];
      const allowed = transitions.filter((status) => !["WITHDRAWN", "DRAFT", "READY_FOR_REVIEW"].includes(status) && transitionLabel[status]);
      return <article className="tracker-row" key={application.id}>
        <div className="tracker-main"><span className="tracker-mark"><ClipboardList size={18} /></span><div><strong className="tracker-title">{application.opportunity?.title || "Saved opportunity"}</strong><p>{application.opportunity?.organization || application.opportunity?.provider || application.opportunity_id}</p><small>Updated {application.created_at ? new Date(application.created_at).toLocaleDateString("en-IN") : "recently"}</small></div></div>
        <div className="tracker-actions"><span className="badge badge-neutral">{APPLICATION_STATUS_LABELS[application.status] || application.status}</span>{allowed.length > 0 && <label className="sr-only" htmlFor={`status-${application.id}`}>Update status for {application.opportunity?.title || "this application"}</label>}{allowed.length > 0 && <select id={`status-${application.id}`} className="status-select" value="" onChange={(event) => event.target.value && updateStatus(application, event.target.value)} disabled={updating === application.id}><option value="">Update status</option>{allowed.map((status) => <option value={status} key={status}>{transitionLabel[status]}</option>)}</select>}{application.opportunity_id && <Link href={`/opportunities/${application.opportunity_id}`} className="icon-link" aria-label="View opportunity"><ArrowUpRight size={16} /></Link>}</div>
        <div className="full-span">
          {application.status === "SAVED" && <button className="button button-secondary" disabled={updating === application.id} onClick={() => updateStatus(application, "DRAFT")}>Prepare application</button>}
          {application.status === "DRAFT" && <><label>Application statement<textarea className="form-control" value={materials[application.id] ?? application.material?.statement ?? ""} onChange={(event) => setMaterials((current) => ({ ...current, [application.id]: event.target.value }))} /></label><button className="button button-secondary" disabled={updating === application.id} onClick={() => act(application, "save")}>Save materials</button><button className="button button-primary" disabled={updating === application.id || (materials[application.id] !== undefined && materials[application.id] !== (application.material?.statement ?? ""))} onClick={() => updateStatus(application, "READY_FOR_REVIEW")}>Review saved materials</button></>}
          {["READY_FOR_REVIEW", "APPROVED"].includes(application.status) && <pre>{JSON.stringify(application.material || {}, null, 2)}</pre>}
          {application.status === "READY_FOR_REVIEW" && <><button className="button button-secondary" onClick={() => updateStatus(application, "DRAFT")}>Edit materials</button><button className="button button-primary" disabled={updating === application.id} onClick={() => act(application, "approve")}>Approve these materials</button></>}
          {application.status === "APPROVED" && <><button className="button button-secondary" disabled={updating === application.id} onClick={() => updateStatus(application, "DRAFT")}>Edit approved materials</button><label><input type="checkbox" checked={!!confirmations[application.id]} onChange={(event) => setConfirmations((current) => ({ ...current, [application.id]: event.target.checked }))} /> I confirm submission of the approved materials</label><button className="button button-primary" disabled={!confirmations[application.id] || updating === application.id} onClick={() => act(application, "submit")}>Confirm and submit</button></>}
          {application.receipt && <p role="status">Receipt: {application.receipt.application_id} · {application.receipt.status_source} · External submission not verified</p>}
        </div>
        {itemErrors[application.id] && <p className="form-error full-span" role="alert">{itemErrors[application.id]}</p>}
      </article>;
    })}</div> : !error ? <div className="empty-state"><ClipboardList size={28} /><h3>Your tracker is empty</h3><p>Save an opportunity to keep its application details and deadline in one place.</p><Link className="button button-primary" href="/opportunities">Discover opportunities</Link></div> : null}
    <p className="disclaimer">The backend uses a lifecycle with review and approval states. This page maps those states to the closest canonical student-facing labels and only sends transitions accepted by the API.</p>
  </ProtectedWorkspace>;
}
