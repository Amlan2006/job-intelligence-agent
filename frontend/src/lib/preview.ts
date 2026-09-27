import type { Opportunity, Resume, Discovery } from "./types";
export const previewResume: Resume = {
  resume_id: "preview-resume",
  filename: "Alex_Morgan_Resume.pdf",
  page_count: 2,
  warnings: [],
  profile: {
    skills: [
      "TypeScript",
      "React",
      "Solidity",
      "Node.js",
      "PostgreSQL",
      "Rust",
    ],
    years_experience: 4,
    projects: [
      {
        name: "Onchain analytics",
        description:
          "A developer dashboard for understanding onchain activity.",
      },
    ],
    employment: [
      { title: "Software Engineer", company: "Independent projects" },
    ],
  },
};
const companies = [
  [
    "Arcana",
    "Infrastructure for a more open internet.",
    "Senior Frontend Engineer",
    "Infrastructure",
    92,
    "A",
  ],
  [
    "Helix",
    "Bringing liquidity to the next generation of DeFi.",
    "Full Stack Engineer",
    "DeFi",
    87,
    "H",
  ],
  [
    "Meridian",
    "The connective layer for onchain finance.",
    "Protocol Engineer",
    "Protocol",
    84,
    "M",
  ],
  [
    "Forma",
    "Making digital ownership feel human.",
    "Frontend Engineer",
    "Consumer",
    78,
    "F",
  ],
] as const;
export const previewOpportunities: Opportunity[] = companies.map(
  ([name, description, title, , score], index) => ({
    opportunity_id: `preview-${index}`,
    resume_id: previewResume.resume_id,
    company: {
      company_id: `preview-company-${index}`,
      research_id: `preview-research-${index}`,
      company_name: name,
      company_domain: `${name.toLowerCase()}.example`,
      company_description: description,
      legitimacy_score: 88 - index * 3,
      assessment: "Strong evidence",
      warnings: ["Illustrative preview data — not real company research"],
      sources: [],
      evidence: [
        {
          evidence_type: "product",
          source_name: "Sample company website",
          source_url: "",
          claim: description,
          extracted_value: description,
          confidence: 0.9,
        },
      ],
    },
    job: {
      title,
      company: name,
      required_skills: ["TypeScript", "React", "Solidity"],
      location: "Remote",
      remote: true,
    },
    match: {
      overall_score: score,
      strong_matches: [{ requirement: "TypeScript" }, { requirement: "React" }],
      partial_matches: [{ requirement: "Solidity" }],
      missing_requirements: [{ requirement: "Rust" }],
      warnings: [],
    },
    contacts: [
      {
        name: ["Jamie Chen", "Sam Rivera", "Taylor Kim", "Jordan Lee"][index],
        role: [
          "Head of Engineering",
          "Technical Recruiter",
          "Co-founder & CTO",
          "Engineering Lead",
        ][index],
        company: name,
        linkedin_url: null,
        x_url: null,
        github_url: null,
        relevance_score: 88 - index * 3,
        relevance_reason:
          "Technical leadership and alignment with your engineering background.",
        technical_skills: ["TypeScript", "React"],
        association: "publicly_reported",
        warnings: ["Sample contact — not a real discovery"],
        evidence: [],
      },
    ],
    outreach: {
      outreach_id: `preview-draft-${index}`,
      contact_name: ["Jamie Chen", "Sam Rivera", "Taylor Kim", "Jordan Lee"][
        index
      ],
      drafts: ["linkedin_connection", "linkedin_dm", "x_dm", "email"].map(
        (channel) => ({
          channel,
          subject:
            channel === "email" ? `Exploring engineering at ${name}` : null,
          body: `Hi ${["Jamie", "Sam", "Taylor", "Jordan"][index]},\n\nI’m interested in the engineering work at ${name}. My background in TypeScript and React, along with my onchain analytics project, seems relevant to your team.\n\nWould you be open to a brief conversation?\n\nAlex`,
          evidence_ids: [],
        }),
      ),
      evidence: [],
      warnings: ["Illustrative draft — preview only"],
    },
    warnings: [],
  }),
);
export const previewDiscovery: Discovery = {
  discovery_id: "preview-run",
  status: "completed",
  started_at: "2026-09-27T09:00:00Z",
  warnings: [],
  skipped_cached: 0,
  results: previewOpportunities
    .slice(0, 3)
    .map((o, i) => ({
      status: "analyzed",
      funding: {
        company_name: o.company.company_name!,
        amount_usd: [12000000, 8500000, 6000000][i],
        round_type: ["Series A", "Seed", "Seed"][i],
        announced_at: "2026-09-24",
        source_url: "",
      },
      opportunity_id: o.opportunity_id,
      ranking: { score: [82, 76, 71][i], evidence_coverage: 80 },
      warnings: [],
    })),
};
