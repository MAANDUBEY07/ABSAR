"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { BookmarkCheck, Search } from "lucide-react";
import ProtectedWorkspace from "@/components/ProtectedWorkspace";
import OpportunityCard from "@/components/OpportunityCard";
import Loading from "@/components/Loading";
import { api } from "@/services/api";
import { CATEGORY_LABELS, OPPORTUNITY_CATEGORIES } from "@/utils/constants";

const PAGE_SIZE = 20;

export default function OpportunitiesPage() {
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
  const [location, setLocation] = useState("");
  const [mode, setMode] = useState("");
  const [page, setPage] = useState(0);
  const [items, setItems] = useState([]);
  const [savedIds, setSavedIds] = useState(() => new Set());
  const [savingIds, setSavingIds] = useState(() => new Set());
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const loadVersion = useRef(0);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    setSearch(params.get("search") || params.get("q") || "");
    setCategory(params.get("category") || "");
    setLocation(params.get("state") || "");
    setMode(params.get("opportunity_mode") || "");
  }, []);

  useEffect(() => {
    api.applications({ limit: 100, offset: 0 }).then((result) => {
      setSavedIds(new Set((Array.isArray(result) ? result : []).map((app) => app.opportunity_id)));
    }).catch(() => {});
  }, []);

  const load = useCallback(async () => {
    const version = ++loadVersion.current;
    setLoading(true); setError(""); setNotice("");
    try {
        const filters = {
          limit: PAGE_SIZE,
          search,
          category,
          state: location,
          opportunity_mode: mode,
        };
        const [result, following] = await Promise.all([
          api.opportunities({ ...filters, offset: page * PAGE_SIZE }),
          api.opportunities({ ...filters, limit: 1, offset: (page + 1) * PAGE_SIZE }),
        ]);
        if (version !== loadVersion.current) return;
        const rows = Array.isArray(result.items) ? result.items : [];
        setItems(rows);
        setHasMore(Array.isArray(following.items) && following.items.length > 0);
    } catch (requestError) {
      if (version !== loadVersion.current) return;
      setItems([]);
      setHasMore(false);
      setError(requestError.message);
    }
    finally { if (version === loadVersion.current) setLoading(false); }
  }, [category, location, mode, page, search]);

  useEffect(() => {
    const timer = setTimeout(load, 250);
    return () => { clearTimeout(timer); loadVersion.current += 1; };
  }, [load]);

  async function saveOpportunity(opportunity) {
    if (savedIds.has(opportunity.id) || savingIds.has(opportunity.id)) return;
    setNotice(""); setError("");
    if (String(opportunity.id).startsWith("demo-")) {
      setNotice("This sample listing cannot be saved. Try again after live opportunities load.");
      return;
    }
    setSavingIds((previous) => new Set(previous).add(opportunity.id));
    try {
      await api.createApplication(opportunity.id);
      setSavedIds((previous) => new Set(previous).add(opportunity.id));
      setNotice("Opportunity saved to your application tracker.");
    } catch (requestError) {
      if (requestError.status === 409) {
        setSavedIds((previous) => new Set(previous).add(opportunity.id));
        setNotice("This opportunity is already in your application tracker.");
      } else setError(requestError.message);
    } finally {
      setSavingIds((previous) => { const next = new Set(previous); next.delete(opportunity.id); return next; });
    }
  }

  return <ProtectedWorkspace>
    <div className="page-heading"><div><span className="eyebrow">DISCOVER</span><h1>Find opportunities</h1><p>Search current listings and use filters supported by the AVSAR API.</p></div><Link className="button button-secondary" href="/applications"><BookmarkCheck size={16} /> My applications</Link></div>
    <form className="filter-toolbar" onSubmit={(event) => { event.preventDefault(); if (page) setPage(0); else load(); }} aria-label="Filter opportunities">
      <label className="searchbar"><Search size={17} aria-hidden="true" /><input value={search} onChange={(event) => { setSearch(event.target.value); setPage(0); }} placeholder="Search titles, organizations or descriptions" aria-label="Search opportunities" /></label>
      <label className="filter-select"><span className="sr-only">Category</span><select value={category} onChange={(event) => { setCategory(event.target.value); setPage(0); }}><option value="">All categories</option>{OPPORTUNITY_CATEGORIES.map((value) => <option value={value} key={value}>{CATEGORY_LABELS[value]}</option>)}</select></label>
      <label className="filter-select"><span className="sr-only">Location</span><input className="filter-location" value={location} onChange={(event) => { setLocation(event.target.value); setPage(0); }} placeholder="State / location" aria-label="Filter by location" /></label>
      <label className="filter-select"><span className="sr-only">Availability mode</span><select value={mode} onChange={(event) => { setMode(event.target.value); setPage(0); }}><option value="">Any mode</option><option value="online">Online</option><option value="offline">On-site</option><option value="hybrid">Hybrid</option></select></label>
    </form>
    {mode && <p className="form-feedback">Showing listings with a confirmed {mode === "offline" ? "on-site" : mode} mode. Listings without mode information are excluded.</p>}
    {notice && <div className="inline-message" role="status">{notice}</div>}
    {error && <div className="inline-message error" role="alert"><span>{error}</span><button className="button button-secondary" type="button" onClick={load} disabled={loading}>Retry</button></div>}
    <div className="results-summary" aria-live="polite" aria-busy={loading}><strong>{loading ? "Loading…" : items.length}</strong><span>opportunities on this page</span></div>
    {loading && !items.length ? <Loading label="Loading opportunities" /> : items.length ? <div className="opportunity-grid">{items.map((item) => <OpportunityCard key={item.id} opportunity={item} matchScore={item.matchScore} saved={savedIds.has(item.id)} saving={savingIds.has(item.id)} onSave={saveOpportunity} />)}</div> : !error ? <div className="empty-state"><h3>No opportunities found</h3><p>Try changing your search or filters. New listings will appear when available from the backend.</p><button className="button button-secondary" type="button" onClick={() => { setSearch(""); setCategory(""); setLocation(""); setMode(""); setPage(0); }}>Clear filters</button></div> : null}
    <nav className="pagination" aria-label="Opportunity pages"><button className="button button-secondary" type="button" onClick={() => setPage((current) => Math.max(0, current - 1))} disabled={page === 0 || loading}>Previous</button><span>Page {page + 1}</span><button className="button button-secondary" type="button" onClick={() => setPage((current) => current + 1)} disabled={!hasMore || loading}>Next</button></nav>
  </ProtectedWorkspace>;
}
