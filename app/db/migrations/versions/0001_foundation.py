"""Initial research and inference tables."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "research_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_table(
        "llm_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("research_run_id", sa.Uuid(), sa.ForeignKey("research_runs.id"), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def downgrade():
    op.drop_table("llm_runs")
    op.drop_table("research_runs")
