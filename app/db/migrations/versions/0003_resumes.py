"""Stored resume text and structured profiles."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "resumes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("content_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("extracted_text", sa.Text(), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_table(
        "resume_profiles",
        sa.Column("resume_id", sa.Uuid(), sa.ForeignKey("resumes.id"), primary_key=True),
        sa.Column("research_run_id", sa.Uuid(), sa.ForeignKey("research_runs.id"), nullable=False),
        sa.Column("profile_json", postgresql.JSONB(), nullable=False),
        sa.Column("warnings", postgresql.JSONB(), nullable=False),
    )


def downgrade():
    op.drop_table("resume_profiles")
    op.drop_table("resumes")
