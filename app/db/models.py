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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LLMRun(Base):
    __tablename__ = "llm_runs"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    research_run_id: Mapped[UUID] = mapped_column(ForeignKey("research_runs.id"))
    metadata_json: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
