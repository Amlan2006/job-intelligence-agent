"""Company records, reports and evidence."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "companies",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("domain", sa.String(253), unique=True, nullable=False),
    )
    op.add_column("research_runs", sa.Column("company_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_research_company", "research_runs", "companies", ["company_id"], ["id"]
    )
    op.add_column("research_runs", sa.Column("report", postgresql.JSONB(), nullable=True))
    op.create_table(
        "company_evidence",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("research_run_id", sa.Uuid(), sa.ForeignKey("research_runs.id"), nullable=False),
        sa.Column("evidence_json", postgresql.JSONB(), nullable=False),
    )
    op.create_index("ix_company_evidence_research_run_id", "company_evidence", ["research_run_id"])


def downgrade():
    op.drop_table("company_evidence")
    op.drop_column("research_runs", "report")
    op.drop_constraint("fk_research_company", "research_runs", type_="foreignkey")
    op.drop_column("research_runs", "company_id")
    op.drop_table("companies")
