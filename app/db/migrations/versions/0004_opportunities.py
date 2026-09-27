"""Jobs, opportunity reports and pgvector embedding cache."""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "jobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("company_id", sa.Uuid(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("profile_json", postgresql.JSONB(), nullable=False),
    )
    op.create_table(
        "opportunities",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("company_id", sa.Uuid(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("resume_id", sa.Uuid(), sa.ForeignKey("resumes.id"), nullable=False),
        sa.Column("job_id", sa.Uuid(), sa.ForeignKey("jobs.id"), nullable=True),
        sa.Column("research_run_id", sa.Uuid(), sa.ForeignKey("research_runs.id"), nullable=False),
        sa.Column("report_json", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_table(
        "skill_embeddings",
        sa.Column("text", sa.Text(), primary_key=True),
        sa.Column("model", sa.String(255), primary_key=True),
        sa.Column("embedding", Vector(), nullable=False),
    )


def downgrade():
    op.drop_table("skill_embeddings")
    op.drop_table("opportunities")
    op.drop_table("jobs")
