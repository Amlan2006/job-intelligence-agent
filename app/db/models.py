from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, func
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
