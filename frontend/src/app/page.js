"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  ArrowRight, ArrowUpRight, BookmarkCheck, BriefcaseBusiness, CalendarDays,
  FileText, FlaskConical, GraduationCap, Handshake, Laptop, Layers3,
  Search, ShieldCheck, Sparkles, Trophy, UsersRound, Zap,
} from "lucide-react";
import { CATEGORY_LABELS, OPPORTUNITY_CATEGORIES } from "@/utils/constants";
import { api } from "@/services/api";
import { useAuth } from "@/hooks/useAuth";
import ThemeToggle from "@/components/ThemeToggle";

const featuredCategories = [
  { title: "Scholarships", category: "scholarship", Icon: GraduationCap, tone: "peach" },
  { title: "Internships", category: "internship", Icon: BriefcaseBusiness, tone: "mint" },
  { title: "Jobs", category: "job", Icon: Laptop, tone: "sand" },
  { title: "Hackathons", category: "hackathon", Icon: Layers3, tone: "cream" },
  { title: "Competitions", category: "coding_competition", Icon: Trophy, tone: "rose" },
  { title: "Fellowships", category: "fellowship", Icon: UsersRound, tone: "mint" },
  { title: "Research", query: "research", Icon: FlaskConical, tone: "cream" },
  { title: "Apprenticeships", category: "apprenticeship", Icon: Handshake, tone: "peach" },
];

const features = [
  { title: "Personalized Discovery", text: "Find opportunities that match your profile and interests.", Icon: Zap },
  { title: "Eligibility Check", text: "Know what fits and what information you may still need.", Icon: ShieldCheck },
  { title: "Resume Analyzer", text: "Review resume skill claims and compare them with requirements.", Icon: FileText },
  { title: "Deadline Tracker", text: "Keep saved opportunities and important dates together.", Icon: CalendarDays },
];

const steps = [
  ["01", "Discover", "Explore student opportunities in one searchable place."],
  ["02", "Check eligibility", "Understand requirements and see what information is missing."],
  ["03", "Analyse your resume", "Compare your skills with the opportunity requirements."],
  ["04", "Track applications", "Save opportunities and keep upcoming deadlines in view."],
];

function StudentIllustration() {
  return (
    <svg className="student-illustration" viewBox="0 0 650 430" role="img" aria-labelledby="student-art-title student-art-description">
      <title id="student-art-title">Student exploring opportunities on a laptop</title>
      <desc id="student-art-description">A student in an orange hoodie works on a laptop surrounded by scholarship, internship and hackathon cards.</desc>
      <defs>
        <linearGradient id="hero-glow" x1="0" x2="1" y1="0" y2="1"><stop stopColor="var(--art-glow)" /><stop offset="1" stopColor="var(--art-glow-end)" /></linearGradient>
        <linearGradient id="hoodie" x1="0" x2="1" y1="0" y2="1"><stop stopColor="#ff9a18" /><stop offset="1" stopColor="#f56b00" /></linearGradient>
        <filter id="card-shadow" x="-30%" y="-30%" width="160%" height="170%"><feDropShadow dx="0" dy="12" stdDeviation="13" floodColor="#000" floodOpacity=".13" /></filter>
      </defs>
      <path d="M78 352c32-74 72-125 138-129 48-3 43-82 108-84 58-2 59 56 115 59 63 3 81-43 136-17 46 21 31 113 75 171H78Z" fill="url(#hero-glow)" />
      <circle cx="451" cy="201" r="157" fill="none" stroke="var(--art-ring)" strokeWidth="2" />
      <circle cx="451" cy="201" r="125" fill="none" stroke="var(--art-ring)" strokeDasharray="4 10" />
      <g className="illustration-opportunity" filter="url(#card-shadow)" transform="rotate(-7 163 130)">
        <rect x="39" y="89" width="208" height="67" rx="16" fill="var(--art-card)" stroke="var(--art-card-border)" strokeWidth="2" />
        <path d="M63 112h28v18H63zM59 111l18-10 18 10M71 130v9m14-9v9" fill="none" stroke="#ff7900" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" />
        <text x="105" y="129" className="illustration-label">Scholarships</text>
      </g>
      <g className="illustration-opportunity" filter="url(#card-shadow)" transform="rotate(-4 145 220)">
        <rect x="20" y="183" width="220" height="66" rx="16" fill="var(--art-card)" stroke="var(--art-card-border)" strokeWidth="2" />
        <rect x="48" y="201" width="28" height="22" rx="3" fill="none" stroke="#ff7900" strokeWidth="4" /><path d="M56 201v-6h12v6m-20 8h28" fill="none" stroke="#ff7900" strokeWidth="4" strokeLinecap="round" />
        <text x="91" y="222" className="illustration-label">Internships</text>
      </g>
      <g className="illustration-opportunity" filter="url(#card-shadow)" transform="rotate(-2 155 307)">
        <rect x="42" y="277" width="196" height="62" rx="16" fill="var(--art-card)" stroke="var(--art-card-border)" strokeWidth="2" />
        <path d="m68 296-11 11 11 11m18-22 11 11-11 11m-4-25-8 28" fill="none" stroke="#ff7900" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" />
        <text x="111" y="315" className="illustration-label">Hackathons</text>
      </g>
      <g className="student-figure">
        <path d="M328 425c11-84 35-116 92-126h87c63 11 92 54 105 126Z" fill="url(#hoodie)" stroke="#121212" strokeWidth="7" strokeLinejoin="round" />
        <path d="m402 301 60 79 61-80-29-23h-68z" fill="#fff2db" stroke="#121212" strokeWidth="6" strokeLinejoin="round" />
        <path d="M411 179c2-62 43-102 99-94 47 7 71 43 62 102l-12 45c-10 33-42 53-73 51-34-2-63-29-70-65z" fill="#ffe0b6" stroke="#121212" strokeWidth="7" />
        <path d="M405 157c-6-43 15-75 41-91 34-20 93-14 122 14 23 22 26 51 13 77l-10-22-14 10-2-28c-21 18-53 25-84 24-26-1-47 8-66 24z" fill="#171717" stroke="#121212" strokeWidth="7" strokeLinejoin="round" />
        <path d="M415 139c-22-14-30-37-18-54 5 19 20 24 32 28m142 18c20-10 31-27 25-46 19 23 14 53-6 71" fill="#171717" stroke="#121212" strokeWidth="7" strokeLinecap="round" />
        <g fill="none" stroke="#171717" strokeWidth="5"><circle cx="450" cy="184" r="21"/><circle cx="518" cy="184" r="21"/><path d="M471 182h26m-63-4h-18m104 0h18"/></g>
        <circle cx="453" cy="184" r="4" fill="#171717"/><circle cx="516" cy="184" r="4" fill="#171717" />
        <path d="M473 212q13 11 26-1m-33 22q12 12 26 4" fill="none" stroke="#171717" strokeWidth="4" strokeLinecap="round" />
        <path d="M395 302q-42 20-57 70l-18 53h57l34-65m119-58q49 10 68 64l19 59h-57l-34-66" fill="url(#hoodie)" stroke="#121212" strokeWidth="7" strokeLinejoin="round" />
        <path d="M402 329q54 67 111 4" fill="none" stroke="#c95600" strokeWidth="5" strokeLinecap="round" />
        <path d="M395 350q39 50 66 52m76-59q-34 37-56 50" fill="none" stroke="#171717" strokeWidth="6" strokeLinecap="round" />
      </g>
      <g filter="url(#card-shadow)">
        <path d="m300 292 217 9 34 117-224-2z" fill="#262626" stroke="#111" strokeWidth="8" strokeLinejoin="round" />
        <path d="m327 309 174 7 23 81-176-1z" fill="#111" />
        <path d="m380 338 17-27h18l-16 27zm24 0 17-27h18l-16 27zm0 4h18l-16 26h-18z" fill="#ff7900" />
        <path d="M312 417h244l-18 13H329z" fill="#555" stroke="#111" strokeWidth="5" strokeLinejoin="round" />
      </g>
      <path d="m599 92 10-24m7 41 23-13m-22 34 27-3" fill="none" stroke="#ff7900" strokeWidth="6" strokeLinecap="round" />
    </svg>
  );
}

const formatDate = (value) => {
  if (!value) return "Deadline not listed";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Deadline not listed" : date.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
};

export default function LandingPage() {
  const { user, loading: authLoading } = useAuth();
  const [featured, setFeatured] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");

  useEffect(() => {
    if (authLoading) return undefined;
    if (!user) { setLoading(false); return undefined; }
    let active = true;
    api.opportunities({ limit: 4, offset: 0 })
      .then((result) => { if (active) setFeatured(Array.isArray(result.items) ? result.items : []); })
      .catch((error) => { if (active) setLoadError(error.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [authLoading, user]);

  return (
    <div className="public-site">
      <header className="public-header">
        <Link href="/" className="public-brand" aria-label="AVSAR home">
          <span className="brand-mark" aria-hidden="true"><svg viewBox="0 0 40 40"><path d="M12 3h10l16 27-5 8H22L6 11z"/><path d="M12 3 6 11h18l-5 8H2m16 0 9 15m-9-15h18"/></svg></span>
          <span className="brand-name">avsar</span><span className="brand-divider"/><span className="brand-tagline">The Student Opportunity Platform</span>
        </Link>
        <nav className="public-nav" aria-label="Main navigation">
          <a href="#categories">Explore</a><a href="#features">Features</a><a href="#how-it-works">How it works</a><a href="#about">About</a>
        </nav>
        <div className="public-actions">
          <ThemeToggle />
          {user ? (
            <Link href="/dashboard" className="header-cta">
              Dashboard <ArrowRight size={16} />
            </Link>
          ) : (
            <>
              <Link href="/login" className="header-login">
                Log in
              </Link>
              <Link href="/signup" className="header-cta">
                Get started <ArrowRight size={16} />
              </Link>
            </>
          )}
        </div>
      </header>

      <main>
        <section className="landing-hero">
          <div className="landing-hero-inner">
            <div className="landing-hero-copy">
              <span className="hero-category-pill"><GraduationCap size={21} /><span>Scholarships · Internships · Jobs · Hackathons · and more</span></span>
              <h1>Find Opportunities<br />That <span>Fit You</span></h1>
              <p>Discover verified opportunities, check your eligibility, analyse your resume and never miss a deadline — all in one place.</p>
              <div className="hero-actions"><Link href="/opportunities" className="hero-primary"><Search size={20} />Explore Opportunities</Link><Link href={user ? "/resume" : "/login"} className="hero-secondary"><FileText size={20} />Analyze Resume</Link></div>
            </div>
            <div className="landing-hero-art"><StudentIllustration /></div>
          </div>
        </section>

        <section className="features-row content-wrap" id="features" aria-label="AVSAR features">
          {features.map(({ title, text, Icon }) => <article className="feature-card" key={title}><span className="feature-icon"><Icon size={29} strokeWidth={2.1} /></span><div><h2>{title}</h2><p>{text}</p></div></article>)}
        </section>

        <section className="category-showcase content-wrap" id="categories">
          <div className="showcase-heading"><h2>Explore by Category</h2><Link href="/opportunities" className="showcase-link">View All Categories <ArrowRight size={17} /></Link></div>
          <div className="showcase-categories">
            {featuredCategories.map(({ title, category, query, Icon, tone }) => <Link href={category ? `/opportunities?category=${encodeURIComponent(category)}` : `/opportunities?q=${encodeURIComponent(query)}`} className={`showcase-category ${tone}`} key={category || query}><Icon size={30} strokeWidth={2} /><span>{title}</span></Link>)}
          </div>
          <p className="all-categories-note">Browse all {OPPORTUNITY_CATEGORIES.length} opportunity categories, including government programmes, innovation challenges and more.</p>
        </section>

        <section className="landing-opportunities content-wrap" id="opportunities">
          <div className="showcase-heading"><div><span className="section-kicker">DISCOVER WHAT’S OPEN</span><h2>Opportunities worth a look</h2></div><Link href="/opportunities" className="showcase-link">Explore opportunities <ArrowRight size={17} /></Link></div>
          {loadError && <div className="inline-message error" role="alert">{loadError}</div>}
          {loading && user ? <div className="opportunity-grid">{[0,1,2,3].map((n) => <div className="opportunity-card" key={n}><p>Loading opportunities…</p></div>)}</div> : user && featured.length ? <div className="opportunity-grid">
            {featured.map((item) => <article className="opportunity-card" key={item.id}><div className="card-topline"><span className="card-category-icon"><GraduationCap size={19} /></span><span className="category-label">{CATEGORY_LABELS[item.category] || item.category}</span></div><h3 className="opportunity-title">{item.title}</h3><p className="organization-name">{item.organization || item.provider || "Organization not listed"}</p><div className="opportunity-meta"><span>{item.remote === true ? "Online" : item.remote === false ? "On-site" : "Mode not listed"}</span><span>{formatDate(item.deadline)}</span></div><div className="card-footer"><span className="deadline-label">{item.stipend == null ? "Details on source page" : `${item.stipend} stipend`}</span><Link className="text-link" href={`/opportunities/${encodeURIComponent(item.id)}`}>View details <ArrowUpRight size={15} /></Link></div></article>)}
          </div> : <div className="opportunities-prompt"><span className="prompt-icon"><BookmarkCheck size={22} /></span><div><strong>{user ? "No opportunities available yet" : "Sign in to see opportunities for you"}</strong><p>{user ? "New listings will appear here as they become available." : "Create your profile to explore listings, check eligibility and save deadlines."}</p></div><Link href={user ? "/opportunities" : "/signup"} className="text-link">{user ? "Browse all opportunities" : "Get started"} <ArrowRight size={15} /></Link></div>}
          <p className="listing-note">Opportunity details come from the AVSAR backend. Confirm requirements with the original source before applying.</p>
        </section>

        <section className="how-section-new" id="how-it-works"><div className="content-wrap how-section-inner"><div className="how-intro"><span className="section-kicker">A CLEARER WAY FORWARD</span><h2>From discovery<br />to <span>your next step.</span></h2><p>AVSAR brings the details together so you can focus on opportunities that fit your goals.</p></div><div className="how-step-grid">{steps.map(([number, title, text]) => <article className="how-step-new" key={number}><span className="how-step-icon">{number}</span><div><b>{number} · {title.toUpperCase()}</b><h3>{title} opportunities</h3><p>{text}</p></div></article>)}</div></div></section>

        <section className="landing-about content-wrap" id="about">
          <div>
            <span className="section-kicker">YOUR OPPORTUNITY DESK</span>
            <h2>Find the opportunity.<br /><span>Make it count.</span></h2>
            <p>One place to discover, understand and keep track of the next step in your journey.</p>
          </div>
          <div className="about-actions">
            <Link href={user ? "/profile" : "/signup"} className="hero-primary">
              {user ? "Update your profile" : "Create your profile"} <ArrowRight size={17} />
            </Link>
            <Link href="/opportunities" className="text-link">Browse opportunities <ArrowUpRight size={15} /></Link>
          </div>
        </section>
      </main>
      <footer className="public-footer content-wrap"><Link href="/" className="footer-logo">avsar</Link><span>The Student Opportunity Platform</span><span className="footer-disclaimer">Always confirm requirements with the original source.</span></footer>
    </div>
  );
}
