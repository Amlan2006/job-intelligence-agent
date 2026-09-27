from datetime import datetime
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ResearchRun(Base):
    __tablename__ = "research_runs"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    status: Mapped[str] = mapped_column(String(30))
    company_id: Mapped[UUID | None] = mapped_column(ForeignKey("companies.id"), nullable=True)
    report: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LLMRun(Base):
    __tablename__ = "llm_runs"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    research_run_id: Mapped[UUID] = mapped_column(ForeignKey("research_runs.id"))
    metadata_json: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Company(Base):
    __tablename__ = "companies"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    domain: Mapped[str] = mapped_column(String(253), unique=True)


class CompanyEvidence(Base):
    __tablename__ = "company_evidence"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    research_run_id: Mapped[UUID] = mapped_column(ForeignKey("research_runs.id"), index=True)
    evidence_json: Mapped[dict] = mapped_column(JSONB)


class Resume(Base):
    __tablename__ = "resumes"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    content_hash: Mapped[str] = mapped_column(String(64), unique=True)
    filename: Mapped[str] = mapped_column(String(255))
    extracted_text: Mapped[str] = mapped_column(Text)
    page_count: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ResumeProfileRecord(Base):
    __tablename__ = "resume_profiles"
    resume_id: Mapped[UUID] = mapped_column(ForeignKey("resumes.id"), primary_key=True)
    research_run_id: Mapped[UUID] = mapped_column(ForeignKey("research_runs.id"))
    profile_json: Mapped[dict] = mapped_column(JSONB)
    warnings: Mapped[list] = mapped_column(JSONB)


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"))
    profile_json: Mapped[dict] = mapped_column(JSONB)


class Opportunity(Base):
    __tablename__ = "opportunities"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"))
    resume_id: Mapped[UUID] = mapped_column(ForeignKey("resumes.id"))
    job_id: Mapped[UUID | None] = mapped_column(ForeignKey("jobs.id"), nullable=True)
    research_run_id: Mapped[UUID] = mapped_column(ForeignKey("research_runs.id"))
    report_json: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SkillEmbedding(Base):
    __tablename__ = "skill_embeddings"
    text: Mapped[str] = mapped_column(Text, primary_key=True)
    model: Mapped[str] = mapped_column(String(255), primary_key=True)
    embedding: Mapped[list[float]] = mapped_column(Vector())
