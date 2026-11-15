"use client";

import { useCallback, useEffect, useState } from "react";
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
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    setSearch(params.get("search") || params.get("q") || "");
    setCategory(params.get("category") || "");
    setLocation(params.get("state") || "");
  }, []);

  useEffect(() => {
    api.applications({ limit: 100, offset: 0 }).then((result) => {
      setSavedIds(new Set((Array.isArray(result) ? result : []).map((app) => app.opportunity_id)));
    }).catch(() => {});
  }, []);

  const load = useCallback(async () => {
    setLoading(true); setError(""); setNotice("");
    try {
      if (mode) {
        const result = await api.recommendations({ remote: mode === "online", limit: 100, offset: 0 });
        const candidates = (Array.isArray(result.items) ? result.items : []).map((row) => ({
          ...row.opportunity,
          matchScore: row.score,
        }));
        const filtered = candidates.filter((item) =>
          (!category || item.category === category)
          && (!location || String(item.location || "").toLowerCase().includes(location.toLowerCase()))
          && (!search || `${item.title || ""} ${item.organization || ""} ${item.description || ""}`.toLowerCase().includes(search.toLowerCase()))
        );
        const start = page * PAGE_SIZE;
        setItems(filtered.slice(start, start + PAGE_SIZE));
        setHasMore(start + PAGE_SIZE < filtered.length);
      } else {
        const filters = {
          limit: PAGE_SIZE,
          search,
          category,
          state: location,
        };
        const [result, following] = await Promise.all([
          api.opportunities({ ...filters, offset: page * PAGE_SIZE }),
          api.opportunities({ ...filters, limit: 1, offset: (page + 1) * PAGE_SIZE }),
        ]);
        const rows = Array.isArray(result.items) ? result.items : [];
        setItems(rows);
        setHasMore(Array.isArray(following.items) && following.items.length > 0);
      }
    } catch (requestError) { setError(requestError.message); setItems([]); setHasMore(false); }
    finally { setLoading(false); }
  }, [category, location, mode, page, search]);

  useEffect(() => { const timer = setTimeout(load, 250); return () => clearTimeout(timer); }, [load]);

  async function saveOpportunity(opportunity) {
    if (savedIds.has(opportunity.id)) return;
    setNotice(""); setError("");
    try {
      await api.createApplication(opportunity.id);
      setSavedIds((previous) => new Set(previous).add(opportunity.id));
      setNotice("Opportunity saved to your application tracker.");
    } catch (requestError) {
      if (requestError.status === 409) {
        setSavedIds((previous) => new Set(previous).add(opportunity.id));
        setNotice("This opportunity is already in your application tracker.");
      } else setError(requestError.message);
    }
  }

  return <ProtectedWorkspace>
    <div className="page-heading"><div><span className="eyebrow">DISCOVER</span><h1>Find opportunities</h1><p>Search current listings and use filters supported by the AVSAR API.</p></div><Link className="button button-secondary" href="/applications"><BookmarkCheck size={16} /> My applications</Link></div>
    <form className="filter-toolbar" onSubmit={(event) => { event.preventDefault(); setPage(0); load(); }}>
      <label className="searchbar"><Search size={17} aria-hidden="true" /><input value={search} onChange={(event) => { setSearch(event.target.value); setPage(0); }} placeholder="Search titles, organizations or descriptions" aria-label="Search opportunities" /></label>
      <label className="filter-select"><span className="sr-only">Category</span><select value={category} onChange={(event) => { setCategory(event.target.value); setPage(0); }}><option value="">All categories</option>{OPPORTUNITY_CATEGORIES.map((value) => <option value={value} key={value}>{CATEGORY_LABELS[value]}</option>)}</select></label>
      <label className="filter-select"><span className="sr-only">Location</span><input className="filter-location" value={location} onChange={(event) => { setLocation(event.target.value); setPage(0); }} placeholder="State / location" aria-label="Filter by location" /></label>
      <label className="filter-select"><span className="sr-only">Availability mode</span><select value={mode} onChange={(event) => { setMode(event.target.value); setPage(0); }}><option value="">Any mode</option><option value="online">Online</option><option value="offline">On-site</option><option value="hybrid" disabled>Hybrid (not provided by current API)</option></select></label>
    </form>
    {mode && <p className="form-feedback">Online and on-site filters use the authenticated recommendations endpoint. Hybrid is unavailable in the current backend contract.</p>}
    {notice && <div className="inline-message" role="status">{notice}</div>}
    {error && <div className="inline-message error" role="alert">{error}</div>}
    <div className="results-summary"><strong>{loading ? "Loading…" : items.length}</strong><span>{mode ? "personalized results on this page" : "opportunities on this page"}</span></div>
    {loading ? <Loading label="Loading opportunities" /> : items.length ? <div className="opportunity-grid">{items.map((item) => <OpportunityCard key={item.id} opportunity={item} matchScore={item.matchScore} saved={savedIds.has(item.id)} onSave={saveOpportunity} />)}</div> : !error ? <div className="empty-state"><h3>No opportunities found</h3><p>Try changing your search or filters. New listings will appear when available from the backend.</p></div> : null}
    <nav className="pagination" aria-label="Opportunity pages"><button className="button button-secondary" type="button" onClick={() => setPage((current) => Math.max(0, current - 1))} disabled={page === 0 || loading}>Previous</button><span>Page {page + 1}</span><button className="button button-secondary" type="button" onClick={() => setPage((current) => current + 1)} disabled={!hasMore || loading}>Next</button></nav>
  </ProtectedWorkspace>;
}
