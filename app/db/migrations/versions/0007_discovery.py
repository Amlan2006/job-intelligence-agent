"""Funding snapshots, discovery runs and durable deduplication checkpoints."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "funding_rounds",
        sa.Column("funding_key", sa.String(64), primary_key=True),
        sa.Column("report_json", postgresql.JSONB(), nullable=False),
    )
    op.create_table(
        "discovery_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("resume_id", sa.Uuid(), sa.ForeignKey("resumes.id"), nullable=False),
        sa.Column("report_json", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_discovery_runs_resume_id", "discovery_runs", ["resume_id"])
    op.create_table(
        "discovery_checkpoints",
        sa.Column("cache_key", sa.String(64), primary_key=True),
        sa.Column("opportunity_id", sa.Uuid(), sa.ForeignKey("opportunities.id"), nullable=False),
    )


def downgrade():
    op.drop_table("discovery_checkpoints")
    op.drop_table("discovery_runs")
    op.drop_table("funding_rounds")
