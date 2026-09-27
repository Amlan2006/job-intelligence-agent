"""Public people, company associations and contact discovery snapshots."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "contact_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("company_id", sa.Uuid(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("research_run_id", sa.Uuid(), sa.ForeignKey("research_runs.id"), nullable=False),
        sa.Column("report_json", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_contact_runs_company_id", "contact_runs", ["company_id"])
    op.create_table(
        "people",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("identity_key", sa.String(64), unique=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
    )
    op.create_table(
        "company_people",
        sa.Column("company_id", sa.Uuid(), sa.ForeignKey("companies.id"), primary_key=True),
        sa.Column("person_id", sa.Uuid(), sa.ForeignKey("people.id"), primary_key=True),
        sa.Column("contact_json", postgresql.JSONB(), nullable=False),
    )


def downgrade():
    op.drop_table("company_people")
    op.drop_table("people")
    op.drop_table("contact_runs")
