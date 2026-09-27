from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class OutreachSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    company_evidence_id: str | None
    resume_evidence_id: str | None


class OutreachRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    opportunity_id: UUID
    contact_index: int = Field(default=0, ge=0, le=9)


class OutreachEvidence(BaseModel):
    id: str
    kind: Literal["company", "resume", "contact"]
    text: str
    source_url: str | None = None


class OutreachDraft(BaseModel):
    channel: Literal["linkedin_connection", "linkedin_dm", "x_dm", "email"]
    subject: str | None
    body: str
    evidence_ids: list[str]


class OutreachReport(BaseModel):
    outreach_id: UUID
    opportunity_id: UUID
    contact_index: int
    contact_name: str
    status: Literal["draft"] = "draft"
    drafts: list[OutreachDraft]
    evidence: list[OutreachEvidence]
    warnings: list[str]
