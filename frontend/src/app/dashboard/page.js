"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight, BookmarkCheck, CalendarDays, FileText, RefreshCw, Sparkles } from "lucide-react";
import ProtectedWorkspace from "@/components/ProtectedWorkspace";
import OpportunityCard from "@/components/OpportunityCard";
import DeadlineCard from "@/components/DeadlineCard";
import Loading from "@/components/Loading";
import { api } from "@/services/api";
import { APPLICATION_STATUS_LABELS } from "@/utils/constants";
import { useAuth } from "@/hooks/useAuth";
import { demoDashboard } from "@/utils/demo-data";

function completion(profile) {
  if (!profile) return 0;
  const checks = [profile.name, profile.date_of_birth, profile.degree, profile.branch, profile.cgpa != null, profile.graduation_year, profile.location, profile.skills?.length];
  return Math.round(checks.filter(Boolean).length / checks.length * 100);
}

function dateLabel(value) {
  if (!value) return "Date not listed";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Date not listed" : date.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

export default function DashboardPage() {
  const { user } = useAuth();
  const [data, setData] = useState(demoDashboard);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [isDemo, setIsDemo] = useState(true);
  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
    const results = await Promise.allSettled([
      api.profile(), api.recommendations({ limit: 4, offset: 0 }),
      api.applications({ limit: 100, offset: 0 }), api.calendar({ limit: 5, offset: 0 }),
      api.notifications({ limit: 5, offset: 0 }),
    ]);
    const failed = results.find((result) => result.status === "rejected");
    if (failed) setError(failed.reason.message);
    setIsDemo(Boolean(failed));
    const get = (index, fallback) => results[index].status === "fulfilled" ? results[index].value : fallback;
    const applicationsValue = get(2, demoDashboard.applications);
    const applications = Array.isArray(applicationsValue) ? applicationsValue : demoDashboard.applications;
    const recent = await Promise.all(applications.slice(0, 5).map(async (application) => {
      if (application.opportunity) return application;
      try { const opportunity = await api.opportunity(application.opportunity_id); return { ...application, opportunity }; }
      catch { return { ...application, opportunity: demoDashboard.applications.find((item) => item.opportunity_id === application.opportunity_id)?.opportunity || null }; }
    }));
    setData({
      profile: get(0, demoDashboard.profile),
      recommendations: get(1, { items: demoDashboard.recommendations }).items || demoDashboard.recommendations,
      applications,
      recent,
      deadlines: Array.isArray(get(3, demoDashboard.deadlines)) ? get(3, demoDashboard.deadlines) : demoDashboard.deadlines,
      notifications: Array.isArray(get(4, demoDashboard.notifications)) ? get(4, demoDashboard.notifications) : demoDashboard.notifications,
    });
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => { load(); }, [load]);

  const apps = data?.applications || [];
  const deadlines = data?.deadlines || [];
  const profilePercent = completion(data?.profile);
  const saved = apps.filter((item) => item.status === "SAVED").length;
  const preparing = apps.filter((item) => ["DRAFT", "READY_FOR_REVIEW", "APPROVED"].includes(item.status)).length;
  const dueSoon = deadlines.filter((item) => {
    const days = Math.ceil((new Date(`${item.deadline}T00:00:00`).getTime() - Date.now()) / 86400000);
    return days >= 0 && days <= 7;
  }).length;

  return <ProtectedWorkspace>
    <div className="page-heading"><div><span className="eyebrow">YOUR WORKSPACE</span><h1>Welcome{data?.profile?.name ? `, ${data.profile.name}` : user?.email ? `, ${user.email.split("@")[0]}` : " back"}</h1><p>Your applications, deadlines and opportunity recommendations in one place.</p></div><div className="dashboard-heading-actions"><button className="button button-secondary" type="button" onClick={load} disabled={loading}><RefreshCw size={15} /> Refresh</button><Link className="button button-primary" href="/opportunities">Explore opportunities <ArrowRight size={15} /></Link></div></div>
    {error && <div className="inline-message error dashboard-error" role="alert"><span>Some dashboard information could not be loaded: {error}</span><button className="button button-secondary" type="button" onClick={load} disabled={loading}>Retry</button></div>}
    {loading && !data ? <Loading label="Loading your dashboard" /> : <>
      <section className="stats-grid" aria-label="Dashboard statistics">
        <article className="stat-card"><span className="stat-icon"><BookmarkCheck /></span><div><small>Saved opportunities</small><strong>{saved}</strong><span>In your application tracker</span></div></article>
        <article className="stat-card"><span className="stat-icon peach"><FileText /></span><div><small>In preparation</small><strong>{preparing}</strong><span>Applications being prepared</span></div></article>
        <article className="stat-card"><span className="stat-icon mint"><CalendarDays /></span><div><small>Deadlines this week</small><strong>{dueSoon}</strong><span>From your saved opportunities</span></div></article>
      </section>
      <section className="dashboard-tip"><Sparkles size={20} /><div><strong>Profile completion · {profilePercent}%</strong><p>Add your education and skills to improve eligibility checks and recommendations.</p></div><Link href="/profile">Update profile <ArrowRight size={14} /></Link></section>
      <section className="content-section"><div className="section-title-row"><div><span className="eyebrow">PERSONALIZED</span><h2>Recommended for you</h2></div><Link className="text-link" href="/opportunities">View all <ArrowRight size={14} /></Link></div>
        {data?.recommendations?.length ? <div className="opportunity-grid">{data.recommendations.map((row) => <OpportunityCard key={row.opportunity_id} opportunity={row.opportunity} matchScore={row.score} saved={apps.some((app) => app.opportunity_id === row.opportunity_id)} />)}</div> : <div className="empty-state"><h3>No recommendations yet</h3><p>Complete your profile and browse available listings to get started.</p></div>}
      </section>
      <section className="dashboard-columns">
        <div className="content-section deadline-section"><div className="section-title-row"><div><span className="eyebrow">STAY ON TRACK</span><h2>Upcoming deadlines</h2></div><Link className="text-link" href="/calendar">Open calendar <ArrowRight size={14} /></Link></div>{deadlines.length ? <div className="deadline-list">{deadlines.map((event) => <DeadlineCard key={event.id} deadline={event.deadline} title={event.title} href={`/opportunities/${event.opportunity_id}`} />)}</div> : <div className="empty-state compact"><h3>No upcoming deadlines</h3><p>Save opportunities to see their dates here.</p></div>}</div>
        <div className="content-section"><div className="section-title-row"><div><span className="eyebrow">RECENT ACTIVITY</span><h2>Applications</h2></div><Link className="text-link" href="/applications">View tracker <ArrowRight size={14} /></Link></div>{data?.recent?.length ? <div className="tracker-list">{data.recent.map((application) => <article className="tracker-row" key={application.id}><div className="tracker-main"><span className="tracker-mark">{(application.opportunity?.title || "A").slice(0, 1)}</span><div><strong className="tracker-title">{application.opportunity?.title || "Opportunity application"}</strong><p>{application.opportunity?.organization || application.opportunity?.provider || "Organization not listed"}</p><small>{dateLabel(application.created_at)}</small></div></div><span className="badge badge-neutral">{APPLICATION_STATUS_LABELS[application.status] || application.status}</span></article>)}</div> : <div className="empty-state compact"><h3>No recent applications</h3><p>Save an opportunity to start tracking it.</p></div>}</div>
      </section>
      <section id="notifications" className="content-section"><div className="section-title-row"><div><span className="eyebrow">UPDATES</span><h2>Notifications</h2></div></div>{data?.notifications?.length ? <ul className="notification-list">{data.notifications.map((item) => <li key={item.id || item.created_at}><strong>{item.title || item.kind || "AVSAR update"}</strong><span>{item.message || item.description || "You have a new update."}</span><small>{dateLabel(item.created_at)}</small></li>)}</ul> : <div className="empty-state compact"><h3>You’re all caught up</h3><p>There are no notifications to show.</p></div>}</section>
    </>}
  </ProtectedWorkspace>;
}
