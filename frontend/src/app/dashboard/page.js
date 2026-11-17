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
import { sectionItems, loadAllPages } from "@/utils/dashboard-sections.mjs";

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
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [isDemo, setIsDemo] = useState(true);
  const [section, setSection] = useState(null);
  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
    const results = await Promise.allSettled([
      api.profile(), api.recommendations({ limit: 4, offset: 0 }),
      loadAllPages(api.applications), loadAllPages(api.calendar),
      api.notifications({ limit: 5, offset: 0 }),
    ]);
    const failed = results.find((result) => result.status === "rejected");
    if (failed) setError(failed.reason.message);
    setIsDemo(Boolean(failed));
    const get = (index, fallback) => results[index].status === "fulfilled" ? results[index].value : fallback;
    const applicationsValue = get(2, []);
    const applications = Array.isArray(applicationsValue) ? applicationsValue : [];
    const enriched = await Promise.all(applications.map(async (application) => {
      if (application.opportunity) return application;
      try { const opportunity = await api.opportunity(application.opportunity_id); return { ...application, opportunity }; }
      catch { return { ...application, opportunity: null }; }
    }));
    const userProfile = results[0].status === "fulfilled" ? results[0].value : null;
    setData({
      profile: userProfile,
      recommendations: get(1, { items: demoDashboard.recommendations }).items || demoDashboard.recommendations,
      applications: enriched,
      recent: enriched.slice(0, 5),
      deadlines: Array.isArray(get(3, [])) ? get(3, []) : [],
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
  const saved = sectionItems("saved", apps, deadlines).length;
  const preparing = sectionItems("preparing", apps, deadlines).length;
  const dueSoon = sectionItems("deadlines", apps, deadlines).length;
  const sectionTitle = { saved: "Saved opportunities", preparing: "In preparation", deadlines: "Deadlines this week" };
  const visibleItems = section ? sectionItems(section, apps, deadlines) : [];

  const displayName = data?.profile?.name || user?.user_metadata?.full_name || user?.user_metadata?.name || (user?.email ? user.email.split("@")[0] : null);

  return <ProtectedWorkspace>
    <div className="page-heading"><div><span className="eyebrow">YOUR WORKSPACE</span><h1>Welcome{displayName ? `, ${displayName}` : " back"}</h1><p>Your applications, deadlines and opportunity recommendations in one place.</p></div><div className="dashboard-heading-actions"><button className="button button-secondary" type="button" onClick={load} disabled={loading}><RefreshCw size={15} /> Refresh</button><Link className="button button-primary" href="/opportunities">Explore opportunities <ArrowRight size={15} /></Link></div></div>
    {error && <div className="inline-message error dashboard-error" role="alert"><span>Some dashboard information could not be loaded: {error}</span><button className="button button-secondary" type="button" onClick={load} disabled={loading}>Retry</button></div>}
    {loading && !data ? <Loading label="Loading your dashboard" /> : <>
      <section className="stats-grid" aria-label="Dashboard statistics">
        <button type="button" className="stat-card stat-card-action" aria-expanded={section === "saved"} aria-controls="dashboard-section" onClick={() => setSection(section === "saved" ? null : "saved")}><span className="stat-icon"><BookmarkCheck /></span><div><small>Saved opportunities</small><strong>{saved}</strong><span>In your application tracker</span></div></button>
        <button type="button" className="stat-card stat-card-action" aria-expanded={section === "preparing"} aria-controls="dashboard-section" onClick={() => setSection(section === "preparing" ? null : "preparing")}><span className="stat-icon peach"><FileText /></span><div><small>In preparation</small><strong>{preparing}</strong><span>Applications being prepared</span></div></button>
        <button type="button" className="stat-card stat-card-action" aria-expanded={section === "deadlines"} aria-controls="dashboard-section" onClick={() => setSection(section === "deadlines" ? null : "deadlines")}><span className="stat-icon mint"><CalendarDays /></span><div><small>Deadlines this week</small><strong>{dueSoon}</strong><span>From your saved opportunities</span></div></button>
      </section>
      {section && <section id="dashboard-section" className="content-section panel" aria-label={sectionTitle[section]}>
        <div className="section-title-row"><h2>{sectionTitle[section]} ({visibleItems.length})</h2><button type="button" className="button button-secondary" onClick={() => setSection(null)}>Close</button></div>
        {loading ? <Loading label="Loading your records" /> : visibleItems.length ? <div className="tracker-list">{visibleItems.map(item => <article className="tracker-row" key={item.id}>
          <div><strong>{item.opportunity?.title || item.title || "Saved opportunity"}</strong><p>{item.opportunity?.organization || item.opportunity_id}</p>{section === "deadlines" ? <small>Deadline: {dateLabel(item.deadline)}</small> : <span className="badge badge-neutral">{APPLICATION_STATUS_LABELS[item.status] || item.status}</span>}</div>
          <div className="tracker-actions"><Link className="button button-secondary" href={`/opportunities/${encodeURIComponent(item.opportunity_id)}`}>View opportunity</Link>{section !== "deadlines" && <Link className="text-link" href="/applications">Manage application <ArrowRight size={14} /></Link>}</div>
        </article>)}</div> : <div className="empty-state compact"><h3>{error ? "Records could not be loaded" : `No ${sectionTitle[section].toLowerCase()} to show`}</h3><p>{error ? "Use Refresh to try loading your records again." : "Matching records will appear here when you save opportunities or prepare applications."}</p></div>}
      </section>}
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
