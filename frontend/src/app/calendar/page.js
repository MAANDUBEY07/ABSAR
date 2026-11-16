"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { CalendarDays, ArrowUpRight } from "lucide-react";
import ProtectedWorkspace from "@/components/ProtectedWorkspace";
import Loading from "@/components/Loading";
import { api } from "@/services/api";
import { APPLICATION_STATUS_LABELS } from "@/utils/constants";
import DemoNotice from "@/components/DemoNotice";
import { demoDeadlines } from "@/utils/demo-data";

function dayParts(value) {
  const date = new Date(`${value}T00:00:00`);
  return Number.isNaN(date.getTime()) ? { day: "—", month: "" } : { day: date.getDate(), month: date.toLocaleDateString("en-IN", { month: "short" }) };
}

export default function CalendarPage() {
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [items, setItems] = useState(demoDeadlines);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [isDemo, setIsDemo] = useState(true);
  const load = useCallback(async (filters = {}) => {
    setLoading(true);
    setError("");
    try {
      const data = await api.calendar({ ...filters, limit: 100, offset: 0 });
      setItems(Array.isArray(data) ? data : []);
      setIsDemo(false);
    } catch (requestError) {
      setError(requestError.message);
      setItems(demoDeadlines.filter((item) => (!filters.start || item.deadline >= filters.start) && (!filters.end || item.deadline <= filters.end)));
      setIsDemo(true);
    }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);
  function submit(event) { event.preventDefault(); load({ start, end }); }

  return <ProtectedWorkspace>
    <div className="page-heading"><div><span className="eyebrow">PLAN AHEAD</span><h1>Deadline calendar</h1><p>Dates are derived from opportunities saved in your application tracker.</p></div></div>
    {isDemo && <DemoNotice>{error ? "The calendar service is unavailable; sample dates remain filterable." : "Sample deadlines are visible while live dates load."}</DemoNotice>}
    <form className="calendar-filters panel" onSubmit={submit}><label><span className="field-label">From</span><input className="form-control" type="date" value={start} onChange={(event) => setStart(event.target.value)} /></label><label><span className="field-label">To</span><input className="form-control" type="date" value={end} onChange={(event) => setEnd(event.target.value)} /></label><button className="button button-primary" type="submit">Filter dates</button><button className="button button-secondary" type="button" onClick={() => { setStart(""); setEnd(""); load(); }}>Clear</button></form>
    <div className="calendar-note"><CalendarDays size={18} /><p>Only application deadlines supplied by saved opportunity records are shown. Calendar export is not provided by the current backend API.</p></div>
    {error && <div className="inline-message error" role="alert"><span>{error}</span><button className="button button-secondary" type="button" onClick={() => load({ start, end })} disabled={loading}>Retry</button></div>}
    {loading && !items.length ? <Loading label="Loading deadlines" /> : items.length ? <div className="calendar-list">{items.map((item) => {
      const date = dayParts(item.deadline);
      return <article className="calendar-row" key={item.id}><span className="calendar-date"><strong>{date.day}</strong><span>{date.month}</span></span><div className="calendar-event"><strong>{item.title || "Application deadline"}</strong><span>{item.application_status ? APPLICATION_STATUS_LABELS[item.application_status] || item.application_status : "Application"}</span></div><Link href={`/opportunities/${item.opportunity_id}`} className="icon-link" aria-label={`View ${item.title || "opportunity"}`}><ArrowUpRight size={16} /></Link></article>;
    })}</div> : !error ? <div className="empty-state"><CalendarDays size={28} /><h3>No deadlines to show</h3><p>Save opportunities with deadlines to see them on your calendar.</p><Link className="button button-primary" href="/opportunities">Explore opportunities</Link></div> : null}
  </ProtectedWorkspace>;
}
