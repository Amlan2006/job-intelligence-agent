"use client";

import {
  useEffect,
  useRef,
  useState,
  useMemo,
  type FormEvent,
  type ReactNode,
} from "react";
import {
  ArrowUpRight,
  ArrowRight,
  Plus,
  Search,
  LayoutDashboard,
  Compass,
  BriefcaseBusiness,
  FileText,
  Users,
  Send,
  Settings2,
  ChevronDown,
  ChevronRight,
  Check,
  CheckCheck,
  X,
  ExternalLink,
  Upload,
  Sparkles,
  SlidersHorizontal,
  Link2,
  Copy,
  CircleHelp,
  Radio,
  RefreshCw,
  LoaderCircle,
  Menu,
  ShieldCheck,
  Globe2,
  MapPin,
  Layers,
  Filter,
  Bookmark,
  CheckCircle2,
  Zap,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { api, safeUrl } from "@/lib/api";
import type {
  Company,
  Contact,
  Discovery,
  Opportunity,
  Outreach,
  Resume,
} from "@/lib/types";
import {
  previewDiscovery,
  previewOpportunities,
  previewResume,
} from "@/lib/preview";
import { Mark, Orbital } from "./brand";

type View =
  | "Overview"
  | "Discover"
  | "Opportunities"
  | "My resume"
  | "Contacts"
  | "Outreach";
const navigation: { name: View; icon: LucideIcon }[] = [
  { name: "Overview", icon: LayoutDashboard },
  { name: "Discover", icon: Compass },
  { name: "Opportunities", icon: BriefcaseBusiness },
  { name: "My resume", icon: FileText },
  { name: "Contacts", icon: Users },
  { name: "Outreach", icon: Send },
];
const labels: Record<string, string> = {
  linkedin_connection: "Connection note",
  linkedin_dm: "LinkedIn DM",
  x_dm: "X message",
  email: "Email",
};
const money = (n: number | null) =>
  n === null
    ? "Undisclosed"
    : new Intl.NumberFormat("en-US", {
        style: "currency",
        currency: "USD",
        notation: "compact",
        maximumFractionDigits: 1,
      }).format(n);
const initials = (name: string) =>
  name
    .split(" ")
    .map((x) => x[0])
    .slice(0, 2)
    .join("");

function Pill({ children, tone = "" }: { children: ReactNode; tone?: string }) {
  return <span className={`pill ${tone}`}>{children}</span>;
}
function SectionHeading({
  eyebrow,
  title,
  children,
}: {
  eyebrow?: string;
  title: string;
  children?: ReactNode;
}) {
  return (
    <div className="section-heading">
      <div>
        {eyebrow && <span className="eyebrow">{eyebrow}</span>}
        <h2>{title}</h2>
      </div>
      {children}
    </div>
  );
}
function Empty({
  icon: Icon,
  title,
  body,
  action,
}: {
  icon: LucideIcon;
  title: string;
  body: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty">
      <div className="empty-icon">
        <Icon size={25} />
      </div>
      <h3>{title}</h3>
      <p>{body}</p>
      {action}
    </div>
  );
}
function OutLink({
  url,
  children,
}: {
  url?: string | null;
  children: ReactNode;
}) {
  const href = safeUrl(url);
  return href ? (
    <a className="text-link" href={href} target="_blank" rel="noreferrer">
      {children}
      <ArrowUpRight size={14} />
    </a>
  ) : (
    <span className="muted">{children}</span>
  );
}
function Warnings({ items }: { items: string[] }) {
  return items.length > 0 ? (
    <details className="warnings">
      <summary>
        {items.length} research note{items.length !== 1 ? "s" : ""} to review
      </summary>
      {items.map((w, i) => (
        <p key={i}>{w.replaceAll("_", " ")}</p>
      ))}
    </details>
  ) : null;
}
function Modal({
  title,
  children,
  onClose,
  drawer = false,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
  drawer?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    d?.showModal();
    return () => d?.close();
  }, []);
  return (
    <dialog
      ref={ref}
      className={drawer ? "modal drawer" : "modal"}
      onCancel={onClose}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      aria-label={title}
    >
      <div className="modal-head">
        <div>
          <span className="eyebrow">LUTHOR WORKSPACE</span>
          <h2>{title}</h2>
        </div>
        <button
          className="icon-button"
          onClick={onClose}
          aria-label="Close dialog"
        >
          <X size={20} />
        </button>
      </div>
      {children}
    </dialog>
  );
}

export default function Workspace() {
  const [view, setView] = useState<View>("Overview");
  const [preview, setPreview] = useState(true);
  const [liveOpportunities, setLiveOpportunities] = useState<Opportunity[]>([]);
  const [liveResume, setLiveResume] = useState<Resume | null>(null);
  const [liveRuns, setLiveRuns] = useState<Discovery[]>([]);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [connection, setConnection] = useState("Not connected");
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("All opportunities");
  const [sort, setSort] = useState("match");
  const [saved, setSaved] = useState<string[]>([]);
  const [mobileNav, setMobileNav] = useState(false);
  const [modal, setModal] = useState<"research" | "settings" | "help" | null>(
    null,
  );
  const [selected, setSelected] = useState<Opportunity | null>(null);
  const [companyReport, setCompanyReport] = useState<Company | null>(null);
  const [detailTab, setDetailTab] = useState("Overview");
  const [copied, setCopied] = useState(false);
  const [channel, setChannel] = useState("linkedin_dm");
  const searchRef = useRef<HTMLInputElement>(null);
  const uploadRef = useRef<HTMLInputElement>(null);
  const opportunities = preview ? previewOpportunities : liveOpportunities;
  const resume = preview ? previewResume : liveResume;
  const runs = preview ? [previewDiscovery] : liveRuns;
  const contacts = opportunities.flatMap((o) =>
    o.contacts.map((contact, index) => ({ contact, index, opportunity: o })),
  );
  const drafts = opportunities.filter((o) => o.outreach);
  const matched = opportunities.filter(
    (o) =>
      o.match?.overall_score !== null && o.match?.overall_score !== undefined,
  );
  const average = matched.length
    ? Math.round(
        matched.reduce((s, o) => s + (o.match?.overall_score || 0), 0) /
          matched.length,
      )
    : null;

  async function refreshLive() {
    setBusy("Connecting your workspace");
    setError("");
    try {
      await api("health/ready");
      setConnection("Connected");
      const items = await api<Opportunity[]>("api/v1/opportunities?limit=100");
      setLiveOpportunities(items);
      const id = localStorage.getItem("luthor-resume") || items[0]?.resume_id;
      if (id) {
        try {
          const r = await api<Resume>(`api/v1/resume/${id}`);
          setLiveResume(r);
          const reports = await api<Discovery[]>(
            `api/v1/discovery/runs?resume_id=${id}`,
          );
          setLiveRuns(reports);
        } catch (e) {
          setLiveResume(null);
          setLiveRuns([]);
          setError((e as Error).message);
        }
      }
    } catch (e) {
      setConnection("Offline");
      setError((e as Error).message);
    } finally {
      setBusy("");
    }
  }
  function switchMode() {
    if (busy) return;
    setPreview(!preview);
    setSelected(null);
    setCompanyReport(null);
    setQuery("");
    setError("");
    setNotice("");
    try {
      localStorage.setItem("luthor-mode", preview ? "live" : "preview");
    } catch {}
    if (preview) void refreshLive();
  }
  useEffect(() => {
    try {
      setSaved(JSON.parse(localStorage.getItem("luthor-saved") || "[]"));
      if (localStorage.getItem("luthor-mode") === "live") {
        setPreview(false);
        void refreshLive();
      }
    } catch {}
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        searchRef.current?.focus();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
    // The persisted workspace choice is read once when the application mounts.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  function navigate(next: View) {
    setView(next);
    setQuery("");
    setMobileNav(false);
    setError("");
  }
  function bookmark(id: string) {
    const next = saved.includes(id)
      ? saved.filter((x) => x !== id)
      : [...saved, id];
    setSaved(next);
    try {
      localStorage.setItem("luthor-saved", JSON.stringify(next));
    } catch {}
  }
  function openOpportunity(o: Opportunity, tab = "Overview") {
    setSelected(o);
    setDetailTab(tab);
    setChannel("linkedin_dm");
    setCopied(false);
  }
  const shown = useMemo(
    () =>
      opportunities
        .filter((o) =>
          `${o.company.company_name} ${o.job?.title || ""} ${o.job?.required_skills.join(" ") || ""}`
            .toLowerCase()
            .includes(query.toLowerCase()),
        )
        .filter((o) => filter !== "Saved" || saved.includes(o.opportunity_id))
        .filter(
          (o) =>
            filter !== "Strong matches" || (o.match?.overall_score || 0) >= 80,
        )
        .sort((a, b) =>
          sort === "name"
            ? (a.company.company_name || "").localeCompare(
                b.company.company_name || "",
              )
            : (b.match?.overall_score ?? -1) - (a.match?.overall_score ?? -1),
        ),
    [opportunities, query, filter, sort, saved],
  );

  async function upload(file: File) {
    if (preview) {
      setError(
        "Switch to your live workspace to upload your resume. Preview uses a sample profile.",
      );
      return;
    }
    if (
      !file.name.toLowerCase().endsWith(".pdf") ||
      file.size > 10 * 1024 * 1024
    ) {
      setError("Please choose a PDF file under 10 MB.");
      return;
    }
    setBusy("Reading your resume and extracting skills");
    setError("");
    try {
      const form = new FormData();
      form.append("file", file);
      const result = await api<Resume>("api/v1/resume/analyze", form);
      setLiveResume(result);
      setLiveRuns([]);
      localStorage.setItem("luthor-resume", result.resume_id);
      setNotice("Your resume is ready. Let’s find where you fit.");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy("");
    }
  }
  async function research(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    if (preview) {
      setModal(null);
      openOpportunity(previewOpportunities[0]);
      setNotice(
        "Showing a sample research report. Switch to live to research a real company.",
      );
      return;
    }
    const company_url = String(form.get("company_url"));
    const job_url = String(form.get("job_url") || "");
    const full = form.get("research_mode") === "opportunity";
    if (full && !resume) {
      setError("Upload your resume before running an opportunity analysis.");
      return;
    }
    setModal(null);
    setBusy(
      full
        ? "Researching the company, matching your skills and finding contacts"
        : "Researching the company and checking sources",
    );
    setError("");
    try {
      if (full) {
        const result = await api<Opportunity>("api/v1/opportunity/analyze", {
          company_url,
          job_url: job_url || null,
          resume_id: resume!.resume_id,
        });
        setLiveOpportunities((prev) => [result, ...prev]);
        openOpportunity(result);
      } else {
        setCompanyReport(
          await api<Company>("api/v1/research/company", { company_url }),
        );
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy("");
    }
  }
  async function discover(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (preview) {
      setNotice(
        "Sample discovery is complete. These results are illustrative.",
      );
      return;
    }
    if (!resume) {
      setError(
        "Upload a resume first so discovery can match companies to you.",
      );
      return;
    }
    const form = new FormData(e.currentTarget);
    setBusy(
      "Searching funding announcements and researching new opportunities",
    );
    setError("");
    try {
      const result = await api<Discovery>("api/v1/discovery/run", {
        resume_id: resume.resume_id,
        source: "tavily",
        lookback_days: Number(form.get("days")),
        limit: Number(form.get("limit")),
        categories: form.get("category") ? [form.get("category")] : [],
      });
      setLiveRuns((prev) => [result, ...prev]);
      setLiveOpportunities(
        await api<Opportunity[]>("api/v1/opportunities?limit=100"),
      );
      setNotice(
        `Discovery ${result.status}. ${result.results.filter((r) => r.status === "analyzed").length} companies researched.`,
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy("");
    }
  }
  async function generate(o: Opportunity, index: number) {
    if (preview) {
      openOpportunity(o, "Outreach");
      return;
    }
    setBusy("Composing an evidence-backed draft");
    setError("");
    try {
      const result = await api<Outreach>("api/v1/outreach/generate", {
        opportunity_id: o.opportunity_id,
        contact_index: index,
      });
      const updated = { ...o, outreach: result };
      setLiveOpportunities((prev) =>
        prev.map((p) => (p.opportunity_id === o.opportunity_id ? updated : p)),
      );
      openOpportunity(updated, "Outreach");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy("");
    }
  }
  async function copy(text: string) {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      setNotice("Clipboard isn’t available. Select the draft text to copy it.");
    }
  }

  function companyEvidence(company: Company) {
    return (
      <>
        <p className="detail-description">
          {company.company_description ||
            "No supported company description available."}
        </p>
        <div className="evidence-score">
          <ShieldCheck size={24} />
          <div>
            <strong>
              {company.legitimacy_score}
              <small>/100</small>
            </strong>
            <span>Company evidence score</span>
          </div>
          <Pill>{company.assessment}</Pill>
        </div>
        <h3 className="minor-heading">Behind the research</h3>
        {company.evidence.length ? (
          company.evidence.map((ev, i) => (
            <div className="evidence" key={i}>
              <span className="eyebrow">
                {ev.evidence_type.replaceAll("_", " ")}
              </span>
              <p>{ev.extracted_value || ev.claim}</p>
              <OutLink url={ev.source_url}>{ev.source_name}</OutLink>
            </div>
          ))
        ) : (
          <p className="muted">No supporting evidence was returned.</p>
        )}
        <Warnings items={company.warnings} />
      </>
    );
  }
  function contactCard(contact: Contact, o: Opportunity, index: number) {
    return (
      <article className="contact-card" key={`${o.opportunity_id}-${index}`}>
        <div className="contact-head">
          <div className="avatar">{initials(contact.name)}</div>
          <span className="contact-score">
            {contact.relevance_score}
            <small> relevance</small>
          </span>
        </div>
        <h3>{contact.name}</h3>
        <p>{contact.role}</p>
        <span className="muted">{contact.company}</span>
        <div className="contact-tags">
          {contact.technical_skills.slice(0, 3).map((s) => (
            <Pill key={s}>{s}</Pill>
          ))}
        </div>
        <p className="contact-note">
          {contact.relevance_reason ||
            "Review the collected evidence before reaching out."}
        </p>
        <div className="contact-actions">
          <OutLink
            url={contact.linkedin_url || contact.x_url || contact.github_url}
          >
            Profile
          </OutLink>
          <button
            disabled={!!busy}
            className="text-link"
            onClick={() => generate(o, index)}
          >
            Draft message <ArrowUpRight size={15} />
          </button>
        </div>
      </article>
    );
  }
  function table(limit?: number) {
    return (
      <div className="opportunity-table">
        <div className="table-header">
          <span>COMPANY / OPPORTUNITY</span>
          <span>SKILL MATCH</span>
          <span>KEY SKILLS</span>
          <span>STATUS</span>
          <span />
        </div>
        {shown.slice(0, limit).map((o, index) => (
          <div className="opportunity-row" key={o.opportunity_id}>
            <button className="company-cell" onClick={() => openOpportunity(o)}>
              <div className={`company-logo logo-${index % 4}`}>
                {(o.company.company_name || "?")[0]}
              </div>
              <div>
                <strong>
                  {o.company.company_name || o.company.company_domain}
                </strong>
                <span>{o.job?.title || "Company research"}</span>
              </div>
            </button>
            <div className="match-cell">
              <strong>
                {o.match?.overall_score == null
                  ? "—"
                  : `${Math.round(o.match.overall_score)}%`}
              </strong>
              <span className="match-track">
                <i style={{ width: `${o.match?.overall_score || 0}%` }} />
              </span>
            </div>
            <div className="skill-cell">
              {(o.job?.required_skills || []).slice(0, 2).map((s) => (
                <Pill key={s}>{s}</Pill>
              ))}
              {!o.job && <span className="muted">Job not provided</span>}
            </div>
            <div className="status-cell">
              <span className={`status-dot ${o.outreach ? "cyan" : ""}`} />
              {o.outreach ? "Ready for outreach" : "Researched"}
            </div>
            <button
              className={`icon-button bookmark ${saved.includes(o.opportunity_id) ? "is-saved" : ""}`}
              onClick={() => bookmark(o.opportunity_id)}
              aria-label={`${saved.includes(o.opportunity_id) ? "Unsave" : "Save"} ${o.company.company_name}`}
            >
              <Bookmark size={16} />
            </button>
          </div>
        ))}
        {!shown.length && (
          <Empty
            icon={BriefcaseBusiness}
            title={
              query
                ? "No matching opportunities"
                : "Your next opportunity starts here"
            }
            body={
              query
                ? "Try another company name or skill."
                : "Research a company or discover recently funded teams to start building your shortlist."
            }
            action={
              <button
                className="button secondary"
                onClick={() => setModal("research")}
              >
                Research a company <ArrowRight size={15} />
              </button>
            }
          />
        )}
      </div>
    );
  }
  const pageDescriptions: Record<View, string> = {
    Overview: "A clearer signal. A more intentional next move.",
    Discover: "Find the teams building what comes next.",
    Opportunities: "Your research, organized around possibility.",
    "My resume": "The experience behind your next chapter.",
    Contacts: "The right people. A more meaningful introduction.",
    Outreach: "Start a conversation with something worth saying.",
  };

  return (
    <div className="workspace">
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      {mobileNav && (
        <button
          className="nav-scrim"
          onClick={() => setMobileNav(false)}
          aria-label="Close navigation"
        />
      )}
      <aside className={`sidebar ${mobileNav ? "mobile-open" : ""}`}>
        <button
          className="brand"
          onClick={() => navigate("Overview")}
          aria-label="Luthor home"
        >
          <Mark />
          <span>
            Luthor<span className="brand-period">.</span>
          </span>
        </button>
        <div className="workspace-switch">
          <div className="workspace-avatar">P</div>
          <div>
            <strong>Personal workspace</strong>
            <span>Your next chapter</span>
          </div>
          <ChevronDown size={14} />
        </div>
        <span className="nav-label">WORKSPACE</span>
        <nav aria-label="Main navigation">
          {navigation.map(({ name, icon: Icon }) => (
            <button
              key={name}
              className={`nav-item ${view === name ? "active" : ""}`}
              onClick={() => navigate(name)}
              aria-current={view === name ? "page" : undefined}
            >
              <Icon size={18} />
              <span>{name}</span>
              {name === "Opportunities" && (
                <span className="nav-count">{opportunities.length}</span>
              )}
              {name === "Discover" && <span className="new-dot" />}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="sidebar-note">
            <div className="little-orbit">
              <Sparkles size={17} />
            </div>
            <strong>Built for your next move.</strong>
            <p>
              Good opportunities start
              <br />
              with better intelligence.
            </p>
            <button onClick={() => navigate("Discover")}>
              Explore discovery <ArrowUpRight size={14} />
            </button>
          </div>
          <button className="nav-item" onClick={() => setModal("settings")}>
            <Settings2 size={18} />
            <span>Workspace settings</span>
          </button>
          <button className="nav-item" onClick={() => setModal("help")}>
            <CircleHelp size={18} />
            <span>How Luthor works</span>
          </button>
          <div className="profile">
            <div className="avatar small">{preview ? "AM" : "ME"}</div>
            <div>
              <strong>{preview ? "Alex Morgan" : "Your workspace"}</strong>
              <span>{preview ? "Preview profile" : "Personal account"}</span>
            </div>
            <span className="profile-dot" />
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumbs">
            <button
              className="icon-button mobile-menu"
              aria-label="Open navigation"
              onClick={() => setMobileNav(true)}
            >
              <Menu size={20} />
            </button>
            <span>Workspace</span>
            <ChevronRight size={13} />
            <strong>{view}</strong>
          </div>
          <div className="topbar-right">
            <div className="global-search">
              <Search size={15} />
              <input
                ref={searchRef}
                aria-label="Search opportunities"
                placeholder="Search anything…"
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value);
                  if (view !== "Overview" && view !== "Opportunities")
                    setView("Opportunities");
                }}
              />
              <kbd>⌘ K</kbd>
            </div>
            <button
              className="mode-button"
              onClick={switchMode}
              disabled={!!busy}
            >
              <span className={`status-dot ${preview ? "" : "cyan"}`} />
              {preview ? "Preview workspace" : "Live workspace"}
              <ChevronDown size={12} />
            </button>
          </div>
        </header>
        <main id="main">
          <div className="page-heading">
            <div>
              <div className="eyebrow">
                <span className="small-line" />
                YOUR OPPORTUNITY INTELLIGENCE
              </div>
              <h1>{view === "Overview" ? "See the opportunity." : view}</h1>
              <p>{pageDescriptions[view]}</p>
            </div>
            <button
              className="button primary"
              onClick={() => setModal("research")}
              disabled={!!busy}
            >
              <Plus size={17} />
              New research
            </button>
          </div>
          <div className={`workspace-notice ${preview ? "" : "live-notice"}`}>
            <span>
              {preview ? (
                <>
                  <span className="status-dot cyan" /> You’re exploring a sample
                  workspace. All companies, people and scores are illustrative.
                </>
              ) : (
                <>
                  <span
                    className={`status-dot ${connection === "Connected" ? "cyan" : ""}`}
                  />
                  Your live workspace · {connection}
                </>
              )}
            </span>
            <button
              onClick={preview ? switchMode : () => void refreshLive()}
              disabled={!!busy}
            >
              {preview ? "Use my workspace" : "Refresh"}
              {preview ? <ArrowUpRight size={13} /> : <RefreshCw size={13} />}
            </button>
          </div>
          {busy && (
            <div className="activity-banner" role="status">
              <LoaderCircle size={18} className="spin" />
              <div>
                <strong>{busy}</strong>
                <span>
                  This can take a few minutes. You can keep browsing this
                  workspace.
                </span>
              </div>
            </div>
          )}
          {error && (
            <div className="alert" role="alert">
              <span>{error}</span>
              <button aria-label="Dismiss error" onClick={() => setError("")}>
                <X size={16} />
              </button>
            </div>
          )}
          {notice && (
            <div className="notice" role="status">
              <CheckCircle2 size={16} />
              <span>{notice}</span>
              <button
                aria-label="Dismiss notification"
                onClick={() => setNotice("")}
              >
                <X size={16} />
              </button>
            </div>
          )}

          {view === "Overview" && (
            <>
              <section className="hero">
                <div className="hero-text">
                  <div className="hero-eyebrow">
                    <span className="status-dot cyan" />
                    LESS NOISE. MORE POSSIBILITY.
                  </div>
                  <h2>
                    Your next move,
                    <br />
                    <span>in sharper focus.</span>
                  </h2>
                  <p>
                    Discover ambitious teams. Understand your fit.
                    <br className="desktop-break" /> Make the right connection.
                  </p>
                  <button
                    className="button hero-button"
                    onClick={() => navigate("Discover")}
                  >
                    Discover opportunities <ArrowUpRight size={17} />
                  </button>
                </div>
                <Orbital />
                <div className="hero-number">01 / INTELLIGENCE AT WORK</div>
              </section>
              <section className="stats" aria-label="Workspace statistics">
                {[
                  {
                    icon: BriefcaseBusiness,
                    label: "Opportunities",
                    value: opportunities.length,
                    note: "In your research workspace",
                  },
                  {
                    icon: Layers,
                    label: "Average skill match",
                    value: average === null ? "—" : `${average}%`,
                    note: "Across analyzed job descriptions",
                  },
                  {
                    icon: Users,
                    label: "Relevant contacts",
                    value: contacts.length,
                    note: "People behind the opportunities",
                  },
                  {
                    icon: Send,
                    label: "Outreach ready",
                    value: drafts.length,
                    note: "Personalized drafts to review",
                  },
                ].map(({ icon: Icon, label, value, note }) => (
                  <div className="stat" key={label}>
                    <div className="stat-label">
                      {label}
                      <Icon size={16} />
                    </div>
                    <div className="stat-value">
                      {value}
                      <span className="stat-spark">
                        <i />
                        <i />
                        <i />
                        <i />
                        <i />
                        <i />
                        <i />
                      </span>
                    </div>
                    <span className="stat-note">{note}</span>
                  </div>
                ))}
              </section>
              <div className="overview-grid">
                <section className="panel opportunities-panel">
                  <SectionHeading
                    title="Your opportunity radar"
                    eyebrow="THE SHORTLIST"
                  >
                    <button
                      className="text-link"
                      onClick={() => navigate("Opportunities")}
                    >
                      View all <ArrowUpRight size={14} />
                    </button>
                  </SectionHeading>
                  <div className="table-tabs">
                    <button
                      className={
                        filter === "All opportunities" ? "selected" : ""
                      }
                      onClick={() => setFilter("All opportunities")}
                    >
                      All opportunities <span>{opportunities.length}</span>
                    </button>
                    <button
                      className={filter === "Strong matches" ? "selected" : ""}
                      onClick={() => setFilter("Strong matches")}
                    >
                      Strong matches
                    </button>
                    <button
                      className={filter === "Saved" ? "selected" : ""}
                      onClick={() => setFilter("Saved")}
                    >
                      Saved
                    </button>
                  </div>
                  {table(4)}
                  <div className="panel-foot">
                    <ShieldCheck size={13} />
                    <span>
                      Every score has a source. Explore the evidence in each
                      report.
                    </span>
                  </div>
                </section>
                <section className="panel profile-panel">
                  <div className="profile-panel-top">
                    <span className="eyebrow">YOUR FOUNDATION</span>
                    <FileText size={18} />
                  </div>
                  <div className="resume-illustration">
                    <div className="paper">
                      <span />
                      <span />
                      <span />
                      <span />
                      <span />
                    </div>
                    <div className="paper-check">
                      <Check size={15} />
                    </div>
                  </div>
                  <h3>
                    {resume
                      ? "Your experience.\nYour advantage."
                      : "Make it personal."}
                  </h3>
                  <p>
                    {resume
                      ? "Your resume is the starting point for every match and introduction."
                      : "Add your resume to discover where your skills can make a difference."}
                  </p>
                  {resume && (
                    <div className="resume-file">
                      <FileText size={15} />
                      <span>{resume.filename}</span>
                      <CheckCircle2 size={13} />
                    </div>
                  )}
                  <button
                    className="button secondary full"
                    onClick={() => navigate("My resume")}
                  >
                    {resume ? "View my profile" : "Upload resume"}
                    <ArrowUpRight size={14} />
                  </button>
                </section>
              </div>
              <section className="funding-section">
                <SectionHeading
                  title="Fresh capital. New possibilities."
                  eyebrow="ON THE HORIZON"
                >
                  <button
                    className="text-link"
                    onClick={() => navigate("Discover")}
                  >
                    Explore discovery <ArrowUpRight size={14} />
                  </button>
                </SectionHeading>
                <div className="funding-grid">
                  {runs[0]?.results.slice(0, 3).map((r, i) => (
                    <button
                      key={i}
                      className="funding-card"
                      onClick={() => {
                        const o = opportunities.find(
                          (o) => o.opportunity_id === r.opportunity_id,
                        );
                        if (o) openOpportunity(o);
                        else navigate("Discover");
                      }}
                    >
                      <div className="funding-top">
                        <span className={`mini-logo logo-${i}`}>
                          {r.funding.company_name[0]}
                        </span>
                        <Pill>{r.funding.round_type || "Funding round"}</Pill>
                        <ArrowUpRight size={17} />
                      </div>
                      <h3>{r.funding.company_name}</h3>
                      <div className="funding-bottom">
                        <strong>
                          {money(r.funding.amount_usd)}
                          <span> raised</span>
                        </strong>
                        <span>
                          {r.funding.announced_at
                            ? new Date(
                                r.funding.announced_at,
                              ).toLocaleDateString("en-US", {
                                month: "short",
                                day: "numeric",
                                timeZone: "UTC",
                              })
                            : "Date unknown"}
                        </span>
                      </div>
                    </button>
                  ))}
                  {!runs[0]?.results.length && (
                    <div className="empty-inline">
                      Run discovery to find recently funded teams.{" "}
                      <button
                        className="text-link"
                        onClick={() => navigate("Discover")}
                      >
                        Get started <ArrowRight size={14} />
                      </button>
                    </div>
                  )}
                </div>
              </section>
            </>
          )}

          {view === "Opportunities" && (
            <section className="panel">
              <SectionHeading title="A shortlist worth your attention">
                <span className="muted">{shown.length} opportunities</span>
              </SectionHeading>
              <div className="filters">
                <label>
                  <Filter size={14} />
                  <select
                    aria-label="Filter opportunities"
                    value={filter}
                    onChange={(e) => setFilter(e.target.value)}
                  >
                    <option>All opportunities</option>
                    <option>Strong matches</option>
                    <option>Saved</option>
                  </select>
                </label>
                <label>
                  <SlidersHorizontal size={14} />
                  <select
                    aria-label="Sort opportunities"
                    value={sort}
                    onChange={(e) => setSort(e.target.value)}
                  >
                    <option value="match">Highest match first</option>
                    <option value="name">Company A–Z</option>
                  </select>
                </label>
              </div>
              {table()}
            </section>
          )}

          {view === "Discover" && (
            <>
              <section className="discovery-intro panel">
                <div>
                  <span className="eyebrow">FOLLOW THE MOMENTUM</span>
                  <h2>
                    The next great team
                    <br />
                    might have just raised.
                  </h2>
                  <p>
                    Find recently funded Web3 startups and let Luthor research
                    the people, the product, and your fit.
                  </p>
                  <div className="discovery-facts">
                    <span>
                      <Globe2 size={15} />
                      Public announcements
                    </span>
                    <span>
                      <ShieldCheck size={15} />
                      Evidence-backed research
                    </span>
                  </div>
                </div>
                <form onSubmit={discover}>
                  <label>
                    Funding announced within
                    <select name="days" defaultValue="90">
                      <option value="30">The last 30 days</option>
                      <option value="90">The last 90 days</option>
                      <option value="180">The last 180 days</option>
                    </select>
                  </label>
                  <div className="form-row">
                    <label>
                      Focus
                      <select name="category">
                        <option value="">All Web3</option>
                        <option>DeFi</option>
                        <option>Infrastructure</option>
                        <option>Gaming</option>
                        <option>DePIN</option>
                      </select>
                    </label>
                    <label>
                      Research limit
                      <select name="limit" defaultValue="3">
                        <option value="1">1 company</option>
                        <option value="3">3 companies</option>
                        <option value="5">5 companies</option>
                      </select>
                    </label>
                  </div>
                  <button
                    disabled={!!busy || (!preview && !resume)}
                    className="button primary full"
                  >
                    <Compass size={17} />
                    {preview ? "Explore sample discovery" : "Start discovery"}
                    <ArrowUpRight size={16} />
                  </button>
                  <span className="form-hint">
                    {!resume
                      ? "Upload a resume first to personalize discovery."
                      : "Search → research → match → connect. We’ll bring it together."}
                  </span>
                </form>
              </section>
              <section className="panel">
                <SectionHeading
                  title="Discovery history"
                  eyebrow="EVERY SIGNAL, SAVED"
                />
                {runs.length ? (
                  runs.map((run) => (
                    <div className="discovery-run" key={run.discovery_id}>
                      <div className="run-heading">
                        <span>
                          <Radio size={15} />
                          {new Date(run.started_at).toLocaleDateString(
                            "en-US",
                            { month: "long", day: "numeric", timeZone: "UTC" },
                          )}
                        </span>
                        <Pill tone="cyan">{run.status}</Pill>
                        <span className="muted">
                          {run.skipped_cached} already researched
                        </span>
                      </div>
                      {run.results.map((r, i) => (
                        <div className="discovery-result" key={i}>
                          <div>
                            <strong>{r.funding.company_name}</strong>
                            <span>
                              {money(r.funding.amount_usd)} ·{" "}
                              {r.funding.round_type || "Round unknown"} ·{" "}
                              {r.status}
                            </span>
                          </div>
                          <div>
                            {r.ranking?.score != null && (
                              <span className="score-label">
                                {r.ranking.score}
                                <small> opportunity score</small>
                              </span>
                            )}
                            <button
                              className="text-link"
                              disabled={!r.opportunity_id}
                              onClick={() => {
                                const o = opportunities.find(
                                  (o) => o.opportunity_id === r.opportunity_id,
                                );
                                if (o) openOpportunity(o);
                                else if (r.opportunity_id)
                                  api<Opportunity>(
                                    `api/v1/opportunities/${r.opportunity_id}`,
                                  )
                                    .then((o) => openOpportunity(o))
                                    .catch((e) => setError(e.message));
                              }}
                            >
                              View research <ArrowUpRight size={14} />
                            </button>
                          </div>
                        </div>
                      ))}
                      {!run.results.length && (
                        <p className="muted">
                          No new results in this run. Previously researched
                          companies are skipped.
                        </p>
                      )}
                      <Warnings items={run.warnings} />
                    </div>
                  ))
                ) : (
                  <Empty
                    icon={Compass}
                    title="A new direction starts with a search"
                    body="Your discovery results and their sources will appear here."
                  />
                )}
              </section>
            </>
          )}

          {view === "My resume" && (
            <div className="resume-grid">
              <section className="panel upload-panel">
                <span className="eyebrow">BUILD YOUR PROFILE</span>
                <h2>
                  Let your work
                  <br />
                  do the talking.
                </h2>
                <p>
                  Upload your resume. Luthor connects your skills and experience
                  to the right opportunities.
                </p>
                <button
                  className="dropzone"
                  disabled={!!busy}
                  onClick={() => uploadRef.current?.click()}
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={(e) => {
                    e.preventDefault();
                    const file = e.dataTransfer.files[0];
                    if (file) void upload(file);
                  }}
                >
                  <div className="empty-icon">
                    <Upload size={24} />
                  </div>
                  <strong>Drop your resume here</strong>
                  <span>or click to browse files</span>
                  <small>PDF · up to 10 MB</small>
                </button>
                <input
                  ref={uploadRef}
                  aria-label="Upload resume PDF"
                  type="file"
                  accept="application/pdf,.pdf"
                  hidden
                  onChange={(e) => {
                    if (e.target.files?.[0]) void upload(e.target.files[0]);
                    e.target.value = "";
                  }}
                />
                <p className="privacy-note">
                  <ShieldCheck size={15} />
                  Your resume is processed by your configured AI provider. Only
                  the resume ID is remembered in this browser.
                </p>
              </section>
              <section className="panel resume-details">
                <SectionHeading title="Your professional fingerprint" />
                {resume ? (
                  <>
                    <div className="resume-file large">
                      <FileText size={21} />
                      <div>
                        <strong>{resume.filename}</strong>
                        <span>
                          {resume.page_count} pages ·{" "}
                          {resume.profile.years_experience ?? "—"} years of
                          experience
                        </span>
                      </div>
                      <Pill tone="cyan">Ready</Pill>
                    </div>
                    <h3 className="minor-heading">Skills & technologies</h3>
                    <div className="tags">
                      {resume.profile.skills.map((s) => (
                        <Pill key={s}>{s}</Pill>
                      ))}
                    </div>
                    <h3 className="minor-heading">Selected projects</h3>
                    {resume.profile.projects.map((p, i) => (
                      <div className="profile-entry" key={i}>
                        <Layers size={18} />
                        <div>
                          <strong>{p.name}</strong>
                          <p>{p.description}</p>
                        </div>
                      </div>
                    ))}
                    <h3 className="minor-heading">Experience</h3>
                    {resume.profile.employment.map((p, i) => (
                      <div className="profile-entry" key={i}>
                        <BriefcaseBusiness size={18} />
                        <div>
                          <strong>{p.title}</strong>
                          <p>{p.company}</p>
                        </div>
                      </div>
                    ))}
                    <Warnings items={resume.warnings} />
                  </>
                ) : (
                  <Empty
                    icon={FileText}
                    title="Your story belongs here"
                    body="Your skills, projects and experience will appear after you upload a resume."
                  />
                )}
              </section>
            </div>
          )}

          {view === "Contacts" && (
            <>
              <div className="content-meta">
                <span>
                  {contacts.length} people across your researched companies
                </span>
                <Pill>
                  <ShieldCheck size={12} />
                  Review current employment before reaching out
                </Pill>
              </div>
              <div className="contact-grid">
                {contacts.map(({ contact, index, opportunity }) =>
                  contactCard(contact, opportunity, index),
                )}
              </div>
              {!contacts.length && (
                <section className="panel">
                  <Empty
                    icon={Users}
                    title="Find the people behind the work"
                    body="Contacts appear after you analyze an opportunity or run discovery."
                    action={
                      <button
                        className="button secondary"
                        onClick={() => setModal("research")}
                      >
                        Start research <ArrowRight size={15} />
                      </button>
                    }
                  />
                </section>
              )}
            </>
          )}

          {view === "Outreach" && (
            <>
              <div className="content-meta">
                <span>{drafts.length} conversations waiting to happen</span>
                <Pill>
                  <CheckCheck size={13} />
                  Drafts only · you choose when to send
                </Pill>
              </div>
              <div className="draft-grid">
                {drafts.map((o) => (
                  <button
                    className="draft-preview panel"
                    key={o.opportunity_id}
                    onClick={() => openOpportunity(o, "Outreach")}
                  >
                    <div className="draft-heading">
                      <span className="avatar small">
                        {initials(o.outreach!.contact_name)}
                      </span>
                      <div>
                        <strong>{o.outreach!.contact_name}</strong>
                        <span>{o.company.company_name}</span>
                      </div>
                      <ArrowUpRight size={17} />
                    </div>
                    <p>
                      {o.outreach!.drafts.find(
                        (d) => d.channel === "linkedin_dm",
                      )?.body || o.outreach!.drafts[0]?.body}
                    </p>
                    <div className="draft-bottom">
                      <Pill tone="cyan">Ready to review</Pill>
                      <span>{o.outreach!.drafts.length} formats</span>
                    </div>
                  </button>
                ))}
              </div>
              {!drafts.length && (
                <section className="panel">
                  <Empty
                    icon={Send}
                    title="A thoughtful first hello"
                    body="Generate an introduction from a researched contact. Every draft stays yours to review."
                    action={
                      <button
                        className="button secondary"
                        onClick={() => navigate("Contacts")}
                      >
                        Explore contacts <ArrowRight size={15} />
                      </button>
                    }
                  />
                </section>
              )}
            </>
          )}
          <footer className="footer">
            <span>
              <Mark /> A LITTLE INTELLIGENCE. A LOT OF POSSIBILITY.
            </span>
            <span>Luthor · Your next move, informed.</span>
          </footer>
        </main>
      </div>

      {modal === "research" && (
        <Modal title="Where should we look?" onClose={() => setModal(null)}>
          <p className="modal-description">
            Start with a company. We’ll connect the dots.
          </p>
          <form className="research-form" onSubmit={research}>
            <label>
              Company website
              <div className="input-icon">
                <Globe2 size={16} />
                <input
                  type="url"
                  name="company_url"
                  placeholder="https://company.com"
                  required
                  autoFocus
                />
              </div>
            </label>
            <label>
              Research type
              <select
                name="research_mode"
                defaultValue={resume ? "opportunity" : "company"}
              >
                <option value="opportunity" disabled={!resume}>
                  Full opportunity analysis
                </option>
                <option value="company">Company research only</option>
              </select>
            </label>
            <label>
              Job posting <span className="muted">optional</span>
              <div className="input-icon">
                <Link2 size={16} />
                <input
                  type="url"
                  name="job_url"
                  placeholder="https://company.com/careers/role"
                />
              </div>
            </label>
            <div className="form-context">
              <FileText size={16} />
              {resume
                ? `Matching against ${resume.filename}`
                : "Upload a resume to enable personalized matching."}
            </div>
            {preview && (
              <p className="form-hint">
                Preview mode opens a sample report. Switch to your live
                workspace for real research.
              </p>
            )}
            <button className="button primary full" disabled={!!busy}>
              {preview ? "Open sample research" : "Start research"}
              <ArrowUpRight size={17} />
            </button>
          </form>
        </Modal>
      )}
      {modal === "settings" && (
        <Modal title="Your workspace" onClose={() => setModal(null)}>
          <div className="settings-content">
            <div className="settings-row">
              <div>
                <strong>Workspace mode</strong>
                <p>
                  {preview
                    ? "Sample data for exploring Luthor"
                    : "Your saved research and resume"}
                </p>
              </div>
              <button
                className="button secondary"
                onClick={() => {
                  switchMode();
                  setModal(null);
                }}
              >
                {preview ? "Connect live" : "Use preview"}
              </button>
            </div>
            <div className="settings-row">
              <div>
                <strong>Backend connection</strong>
                <p>{connection}</p>
              </div>
              <span className="status-dot cyan" />
            </div>
            <p className="muted">
              Luthor connects to your local FastAPI service. Set BACKEND_URL in
              frontend/.env.local to change its address. API keys remain in your
              backend configuration.
            </p>
            <div className="settings-row">
              <div>
                <strong>Saved shortlist</strong>
                <p>Bookmarks are stored in this browser.</p>
              </div>
              <span>{saved.length}</span>
            </div>
          </div>
        </Modal>
      )}
      {modal === "help" && (
        <Modal
          title="From possibility to a plan."
          onClose={() => setModal(null)}
        >
          <div className="help-steps">
            {[
              [
                "01",
                "Make it personal",
                "Upload a PDF resume so Luthor understands your skills and experience.",
              ],
              [
                "02",
                "Follow the signal",
                "Research a company or discover recently funded teams.",
              ],
              [
                "03",
                "Find your fit",
                "Review the evidence, skill matches, gaps, and relevant people.",
              ],
              [
                "04",
                "Start a conversation",
                "Review a personalized draft, copy it, and send it yourself.",
              ],
            ].map(([n, title, body]) => (
              <div key={n}>
                <span>{n}</span>
                <div>
                  <h3>{title}</h3>
                  <p>{body}</p>
                </div>
              </div>
            ))}
          </div>
        </Modal>
      )}
      {companyReport && (
        <Modal
          title={companyReport.company_name || "Company research"}
          onClose={() => setCompanyReport(null)}
          drawer
        >
          <div className="drawer-body">{companyEvidence(companyReport)}</div>
        </Modal>
      )}
      {selected && (
        <Modal
          title={selected.company.company_name || "Opportunity"}
          onClose={() => setSelected(null)}
          drawer
        >
          <div className="drawer-tabs">
            {["Overview", "Evidence", "Contacts", "Outreach"].map((t) => (
              <button
                className={detailTab === t ? "selected" : ""}
                key={t}
                onClick={() => setDetailTab(t)}
              >
                {t}
              </button>
            ))}
          </div>
          <div className="drawer-body">
            {preview && (
              <div className="sample-label">
                ILLUSTRATIVE PREVIEW · NOT LIVE RESEARCH
              </div>
            )}
            {detailTab === "Overview" && (
              <>
                <span className="eyebrow">THE OPPORTUNITY</span>
                <h3 className="role-title">
                  {selected.job?.title || "Company research"}
                </h3>
                <p className="muted location">
                  <MapPin size={14} />
                  {selected.job?.location || "Location not specified"}
                </p>
                <div className="large-match">
                  <span>
                    {selected.match?.overall_score == null
                      ? "—"
                      : `${Math.round(selected.match.overall_score)}%`}
                  </span>
                  <div>
                    <strong>Your skill match</strong>
                    <p>Based on your resume and the job’s requirements.</p>
                  </div>
                </div>
                {selected.match ? (
                  <>
                    <h3 className="minor-heading">Where you align</h3>
                    <div className="tags">
                      {selected.match.strong_matches.map((s, i) => (
                        <Pill tone="cyan" key={i}>
                          <Check size={12} />
                          {s.requirement}
                        </Pill>
                      ))}
                    </div>
                    <h3 className="minor-heading">Room to grow</h3>
                    <div className="tags">
                      {[
                        ...selected.match.partial_matches,
                        ...selected.match.missing_requirements,
                      ].map((s, i) => (
                        <Pill key={i}>{s.requirement}</Pill>
                      ))}
                    </div>
                  </>
                ) : (
                  <p className="muted">
                    Add a specific job posting to get a skill match.
                  </p>
                )}
                <h3 className="minor-heading">About the team</h3>
                <p className="detail-description">
                  {selected.company.company_description ||
                    "Description unavailable."}
                </p>
                <button
                  className="button secondary full"
                  onClick={() => setDetailTab("Evidence")}
                >
                  Explore the research <ArrowRight size={15} />
                </button>
                <Warnings items={selected.warnings} />
              </>
            )}
            {detailTab === "Evidence" && companyEvidence(selected.company)}
            {detailTab === "Contacts" && (
              <>
                {selected.contacts.map((c, i) => (
                  <div key={i}>
                    {contactCard(c, selected, i)}
                    <Warnings items={c.warnings} />
                    {c.evidence.map((e, j) => (
                      <div className="evidence" key={j}>
                        <p>{e.quote}</p>
                        <OutLink url={e.source_url}>Source</OutLink>
                      </div>
                    ))}
                  </div>
                ))}
                {!selected.contacts.length && (
                  <Empty
                    icon={Users}
                    title="No supported contacts yet"
                    body="The research didn’t find enough evidence to identify a relevant contact."
                  />
                )}
              </>
            )}
            {detailTab === "Outreach" &&
              (selected.outreach ? (
                <>
                  <div className="draft-to">
                    <span className="eyebrow">TO</span>
                    <strong>{selected.outreach.contact_name}</strong>
                    <Pill tone="cyan">Draft</Pill>
                  </div>
                  <div className="channel-tabs">
                    {selected.outreach.drafts.map((d) => (
                      <button
                        className={channel === d.channel ? "selected" : ""}
                        key={d.channel}
                        onClick={() => {
                          setChannel(d.channel);
                          setCopied(false);
                        }}
                      >
                        {labels[d.channel] || d.channel}
                      </button>
                    ))}
                  </div>
                  {(() => {
                    const d =
                      selected.outreach!.drafts.find(
                        (x) => x.channel === channel,
                      ) || selected.outreach!.drafts[0];
                    return d ? (
                      <>
                        {d.subject && (
                          <div className="draft-subject">{d.subject}</div>
                        )}
                        <div className="draft-body">{d.body}</div>
                        <div className="draft-tools">
                          <span>{d.body.length} characters</span>
                          <button
                            className="button primary"
                            onClick={() =>
                              copy(
                                `${d.subject ? `Subject: ${d.subject}\n\n` : ""}${d.body}`,
                              )
                            }
                          >
                            {copied ? <Check size={15} /> : <Copy size={15} />}{" "}
                            {copied ? "Copied" : "Copy draft"}
                          </button>
                        </div>
                      </>
                    ) : null;
                  })()}
                  <p className="form-hint">
                    Review the facts and personalize your introduction before
                    sending.
                  </p>
                  {selected.outreach.evidence.length > 0 && (
                    <details className="draft-evidence">
                      <summary>Evidence used in this draft</summary>
                      {selected.outreach.evidence.map((e) => (
                        <div className="evidence" key={e.id}>
                          <p>{e.text}</p>
                          {e.source_url && (
                            <OutLink url={e.source_url}>Source</OutLink>
                          )}
                        </div>
                      ))}
                    </details>
                  )}
                  <Warnings items={selected.outreach.warnings} />
                </>
              ) : (
                <Empty
                  icon={Send}
                  title="Make the first move"
                  body="Choose a researched contact to generate an evidence-backed introduction."
                  action={
                    <button
                      className="button secondary"
                      onClick={() => setDetailTab("Contacts")}
                    >
                      Choose a contact <ArrowRight size={15} />
                    </button>
                  }
                />
              ))}
          </div>
        </Modal>
      )}
    </div>
  );
}
