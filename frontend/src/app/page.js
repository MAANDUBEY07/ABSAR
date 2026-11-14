import Link from "next/link";
import {
  ArrowRight, ArrowUpRight, Search, BriefcaseBusiness, GraduationCap,
  Trophy, FlaskConical, Handshake, Laptop, Landmark, Lightbulb, Rocket, Gift,
  ShieldCheck, CalendarCheck, FileText, Target, MapPin, Clock3, Sparkles
} from "lucide-react";
import { DEMO_OPPORTUNITIES, CATEGORY_LABELS } from "@/utils/constants";

const categories = [
  { title: "Scholarships", subtitle: "Financial support", icon: GraduationCap, color: "mint", filter: "SCHOLARSHIP" },
  { title: "Internships", subtitle: "Build real experience", icon: BriefcaseBusiness, color: "peach", filter: "INTERNSHIP" },
  { title: "Jobs & more", subtitle: "Find your next step", icon: Laptop, color: "sand", filter: "OTHER" },
  { title: "Government schemes", subtitle: "Public programmes", icon: Landmark, color: "sage", filter: "OTHER" },
  { title: "Fellowships", subtitle: "Learn and contribute", icon: Handshake, color: "rose", filter: "FELLOWSHIP" },
  { title: "Apprenticeships", subtitle: "Learn on the job", icon: Laptop, color: "sand", filter: "INTERNSHIP" },
  { title: "Hackathons", subtitle: "Build with a team", icon: Trophy, color: "yellow", filter: "HACKATHON" },
  { title: "Coding challenges", subtitle: "Test your skills", icon: Lightbulb, color: "mint", filter: "HACKATHON" },
  { title: "Research", subtitle: "Explore new ideas", icon: FlaskConical, color: "sage", filter: "RESEARCH" },
  { title: "Startup challenges", subtitle: "Turn ideas into action", icon: Rocket, color: "peach", filter: "OTHER" },
  { title: "Grants", subtitle: "Support for projects", icon: Gift, color: "sand", filter: "SCHOLARSHIP" },
];

const formatDate = (value) => {
  if (!value) return "Deadline not listed";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Deadline not listed" : date.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
};

export default function LandingPage() {
  const featured = DEMO_OPPORTUNITIES.slice(0, 4);
  return (
    <div className="public-site">
      <header className="public-header">
        <Link href="/" className="public-brand" aria-label="AVSAR home">
          <span>avsar</span><ArrowUpRight className="brand-arrow" size={17} strokeWidth={3} />
        </Link>
        <nav className="public-nav" aria-label="Main navigation">
          <Link className="active" href="/opportunities">Discover</Link>
          <Link href="/applications">My Applications</Link>
          <Link href="/resume">Resume Analyzer</Link>
          <Link href="/dashboard">My Dashboard</Link>
        </nav>
        <div className="public-actions">
          <Link href="/opportunities" className="header-icon-link" aria-label="Search opportunities"><Search size={19} /></Link>
          <Link href="/login" className="header-login">Log in</Link>
          <Link href="/signup" className="header-cta">Get started <ArrowRight size={15} /></Link>
        </div>
      </header>

      <main>
        <section className="discovery-hero">
          <div className="discovery-hero-inner">
            <div className="hero-copy-new">
              <span className="platform-pill"><span className="pill-dot" /> THE STUDENT OPPORTUNITY PLATFORM</span>
              <h1>Your next opportunity<br /><span>is just a search away.</span></h1>
              <p className="hero-description">Discover scholarships, internships, hackathons, fellowships and more — all in one place, with the details you need to apply confidently.</p>
              <form className="hero-search" action="/opportunities" method="GET">
                <label className="hero-search-input"><Search size={20} /><input name="q" placeholder="Search opportunities, skills, organisations..." aria-label="Search opportunities" /></label>
                <label className="hero-search-category"><span className="sr-only">Category</span><select name="category" defaultValue=""><option value="">All categories</option>{Object.entries(CATEGORY_LABELS).map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>
                <button type="submit" className="hero-search-button">Search <ArrowRight size={17} /></button>
              </form>
              <div className="hero-trust-line"><ShieldCheck size={15} /><span>Clear eligibility information</span><i /> <span>Trust signals</span><i /> <span>Deadline tracking</span></div>
            </div>

            <div className="hero-visual" aria-label="Illustration of opportunities organised in one place">
              <div className="visual-orbit orbit-one" /><div className="visual-orbit orbit-two" />
              <div className="visual-leaf leaf-one" /><div className="visual-leaf leaf-two" />
              <div className="visual-note"><Sparkles size={14} /> FIND YOUR NEXT STEP</div>
              <div className="visual-main-card">
                <div className="visual-card-top"><span className="visual-brand-dot" /> AVSAR PICKS <span className="visual-status">FOR YOU</span></div>
                <div className="visual-card-art"><div className="art-ring"><GraduationCap size={52} strokeWidth={1.6} /></div><div className="art-spark spark-a">✦</div><div className="art-spark spark-b">✳</div></div>
                <div className="visual-card-copy"><strong>Make your next move count.</strong><span>Opportunities that match your interests.</span></div>
                <div className="visual-card-footer"><span>DISCOVER</span><ArrowUpRight size={17} /></div>
              </div>
              <div className="visual-float-card float-card-top"><span className="float-icon green"><ShieldCheck size={17} /></span><span><b>Eligibility clarity</b><small>Know where you stand</small></span></div>
              <div className="visual-float-card float-card-bottom"><span className="float-icon orange"><CalendarCheck size={17} /></span><span><b>Deadline reminders</b><small>Stay one step ahead</small></span></div>
              <div className="visual-sticker">LESS SEARCHING.<br />MORE APPLYING.</div>
            </div>
          </div>
        </section>

        <section className="categories-section content-wrap">
          <div className="section-heading-row"><div><span className="section-kicker">START WITH WHAT INTERESTS YOU</span><h2>Explore opportunities</h2><p>Choose a path. Find the next step.</p></div><Link href="/opportunities" className="section-view-link">View all opportunities <ArrowRight size={15} /></Link></div>
          <div className="category-grid">
            {categories.map(({ title, subtitle, icon: Icon, color, filter }) => (
              <Link href={`/opportunities?category=${filter}`} className={`category-tile ${color}`} key={title}>
                <span className="category-icon"><Icon size={27} strokeWidth={1.8} /></span>
                <span className="category-copy"><strong>{title}</strong><small>{subtitle}</small></span>
                <span className="category-arrow"><ArrowUpRight size={17} /></span>
              </Link>
            ))}
          </div>
        </section>

        <section className="recommended-section content-wrap">
          <div className="section-heading-row"><div><span className="section-kicker">A FEW PLACES TO START</span><h2>Opportunities worth a look</h2><p>Sample listings to show how AVSAR brings the details together.</p></div><Link href="/opportunities" className="section-view-link">Browse all <ArrowRight size={15} /></Link></div>
          <div className="recommended-grid">
            {featured.map((item, index) => (
              <article className="recommend-card" key={item.id}>
                <div className={`recommend-mark mark-${index + 1}`}>{index === 0 ? <BriefcaseBusiness size={24} /> : index === 1 ? <Handshake size={24} /> : index === 2 ? <GraduationCap size={24} /> : <Trophy size={24} />}</div>
                <div className="recommend-content">
                  <div className="recommend-tags"><span>{CATEGORY_LABELS[item.category] || item.category}</span><span className="trust-tag">{item.trust?.status === "LOW_RISK_INDICATORS" ? "Trust signals available" : item.trust?.status === "NEEDS_REVIEW" ? "Review recommended" : "Not yet assessed"}</span></div>
                  <h3>{item.title}</h3><p className="recommend-org">{item.organization}</p>
                  <div className="recommend-meta"><span><MapPin size={13} />{item.location || "Location varies"}</span><span><Clock3 size={13} />{formatDate(item.deadline)}</span></div>
                  <div className="recommend-bottom"><strong>{item.stipend || "Details on source page"}</strong><Link href={`/opportunities/${item.id}`} aria-label={`View ${item.title}`}><ArrowUpRight size={17} /></Link></div>
                </div>
              </article>
            ))}
          </div>
          <p className="listing-note">These are fictional sample listings for the prototype. Live opportunity discovery and verification require the AVSAR backend.</p>
        </section>

        <section className="how-section-new">
          <div className="content-wrap how-section-inner">
            <div className="how-intro"><span className="section-kicker">HOW AVSAR WORKS</span><h2>From discovery<br />to <span>application.</span></h2><p>One place to find opportunities, understand requirements and keep your next steps organised.</p></div>
            <div className="how-step-grid">
              <div className="how-step-new"><span className="how-step-icon"><Search size={22} /></span><div><b>01 · DISCOVER</b><h3>Find relevant opportunities</h3><p>Explore selected sources in one searchable place.</p></div></div>
              <div className="how-step-new"><span className="how-step-icon orange"><Target size={22} /></span><div><b>02 · CHECK</b><h3>Understand eligibility</h3><p>See the criteria and what still needs confirmation.</p></div></div>
              <div className="how-step-new"><span className="how-step-icon yellow"><FileText size={22} /></span><div><b>03 · PREPARE</b><h3>Improve your application</h3><p>Compare your resume with the opportunity requirements.</p></div></div>
              <div className="how-step-new"><span className="how-step-icon sage"><CalendarCheck size={22} /></span><div><b>04 · TRACK</b><h3>Keep deadlines visible</h3><p>Save opportunities and organise application dates.</p></div></div>
            </div>
          </div>
        </section>

        <section className="bottom-banner content-wrap"><div><span className="section-kicker">YOUR NEXT STEP STARTS HERE</span><h2>Find the opportunity.<br /><span>Make it count.</span></h2></div><Link href="/signup" className="banner-button">Create your profile <ArrowRight size={17} /></Link></section>
      </main>
      <footer className="public-footer content-wrap"><Link href="/" className="footer-logo">avsar<ArrowUpRight size={13} /></Link><span>Discover more. Apply smarter.</span><span className="footer-disclaimer">A student opportunity assistant · Hackathon prototype</span></footer>
    </div>
  );
}
