"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowUpRight, ClipboardList, RefreshCw } from "lucide-react";
import ProtectedWorkspace from "@/components/ProtectedWorkspace";
import Loading from "@/components/Loading";
import { api } from "@/services/api";
import { APPLICATION_STATUS_LABELS, BACKEND_APPLICATION_TRANSITIONS } from "@/utils/constants";

const transitionLabel = {
  DRAFT: "PREPARING",
  READY_FOR_REVIEW: "PREPARING · ready for review",
  ASSESSMENT: "APPLIED · assessment",
  INTERVIEW: "SHORTLISTED · interview",
  OFFER: "SELECTED · offer",
  REJECTED: "REJECTED",
};

export default function ApplicationsPage() {
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

  return <ProtectedWorkspace>
    <div className="page-heading"><div><span className="eyebrow">YOUR PROGRESS</span><h1>My applications</h1><p>Track saved opportunities and update statuses supported by the current application API.</p></div><button className="button button-secondary" type="button" onClick={load} disabled={loading}><RefreshCw size={15} /> Refresh</button></div>
    {error && <div className="inline-message error" role="alert">{error}</div>}
    {notice && <div className="inline-message" role="status">{notice}</div>}
    {loading ? <Loading label="Loading your applications" /> : items.length ? <div className="tracker-list">{items.map((application) => {
      const transitions = BACKEND_APPLICATION_TRANSITIONS[application.status] || [];
      const allowed = transitions.filter((status) => status !== "WITHDRAWN" && transitionLabel[status]);
      return <article className="tracker-row" key={application.id}>
        <div className="tracker-main"><span className="tracker-mark"><ClipboardList size={18} /></span><div><strong className="tracker-title">{application.opportunity?.title || "Saved opportunity"}</strong><p>{application.opportunity?.organization || application.opportunity?.provider || application.opportunity_id}</p><small>Updated {application.created_at ? new Date(application.created_at).toLocaleDateString("en-IN") : "recently"}</small></div></div>
        <div className="tracker-actions"><span className="badge badge-neutral">{APPLICATION_STATUS_LABELS[application.status] || application.status}</span>{allowed.length > 0 && <label className="sr-only" htmlFor={`status-${application.id}`}>Update status for {application.opportunity?.title || "this application"}</label>}{allowed.length > 0 && <select id={`status-${application.id}`} className="status-select" value="" onChange={(event) => event.target.value && updateStatus(application, event.target.value)} disabled={updating === application.id}><option value="">Update status</option>{allowed.map((status) => <option value={status} key={status}>{transitionLabel[status]}</option>)}</select>}{application.opportunity_id && <Link href={`/opportunities/${application.opportunity_id}`} className="icon-link" aria-label="View opportunity"><ArrowUpRight size={16} /></Link>}</div>
        {itemErrors[application.id] && <p className="form-error full-span" role="alert">{itemErrors[application.id]}</p>}
      </article>;
    })}</div> : !error ? <div className="empty-state"><ClipboardList size={28} /><h3>Your tracker is empty</h3><p>Save an opportunity to keep its application details and deadline in one place.</p><Link className="button button-primary" href="/opportunities">Discover opportunities</Link></div> : null}
    <p className="disclaimer">The backend uses a lifecycle with review and approval states. This page maps those states to the closest canonical student-facing labels and only sends transitions accepted by the API.</p>
  </ProtectedWorkspace>;
}
