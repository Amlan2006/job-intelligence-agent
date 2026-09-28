export type Evidence = {
  evidence_type: string;
  source_name: string;
  source_url: string;
  claim: string;
  extracted_value: string | null;
  confidence: number;
};
export type Company = {
  company_id: string;
  research_id: string;
  company_name: string | null;
  company_domain: string;
  company_description: string | null;
  legitimacy_score: number;
  assessment: string;
  evidence: Evidence[];
  sources: string[];
  warnings: string[];
};
export type Contact = {
  name: string;
  role: string;
  company: string;
  linkedin_url: string | null;
  x_url: string | null;
  github_url: string | null;
  relevance_score: number;
  relevance_reason: string;
  technical_skills: string[];
  association: string;
  warnings: string[];
  evidence: { quote: string; source_url: string }[];
};
export type Draft = {
  channel: string;
  subject: string | null;
  body: string;
  evidence_ids: string[];
};
export type Outreach = {
  outreach_id: string;
  contact_name: string;
  drafts: Draft[];
  evidence: { id: string; text: string; source_url: string | null }[];
  warnings: string[];
};
export type Match = {
  overall_score: number | null;
  strong_matches: { requirement: string }[];
  partial_matches: { requirement: string }[];
  missing_requirements: { requirement: string }[];
  warnings: string[];
};
export type Opportunity = {
  opportunity_id: string;
  resume_id: string;
  company: Company;
  job: {
    title: string | null;
    company: string | null;
    required_skills: string[];
    location: string | null;
    remote: boolean | null;
  } | null;
  match: Match | null;
  contacts: Contact[];
  outreach: Outreach | null;
  warnings: string[];
};
export type Resume = {
  resume_id: string;
  filename: string;
  page_count: number;
  warnings: string[];
  profile: {
    skills: string[];
    years_experience: number | null;
    projects: { name: string; description: string }[];
    employment: { company: string; title: string }[];
  };
};
export type Discovery = {
  source?: string;
  discovery_id: string;
  status: string;
  started_at: string;
  warnings: string[];
  skipped_cached: number;
  results: {
    status: string;
    funding: {
      funding_status?: "verified" | "unverified";
      company_url?: string | null;
      website_status?: "verified" | "unverified" | "unreachable";
      job_url?: string | null;
      company_name: string;
      amount_usd: number | null;
      round_type: string | null;
      announced_at: string | null;
      source_url: string;
    };
    opportunity_id: string | null;
    ranking: { score: number | null; evidence_coverage: number } | null;
    warnings: string[];
  }[];
};
