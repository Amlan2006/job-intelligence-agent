"""Evidence-backed, manual-review outreach drafts."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "outreach_messages",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("opportunity_id", sa.Uuid(), sa.ForeignKey("opportunities.id"), nullable=False),
        sa.Column("research_run_id", sa.Uuid(), sa.ForeignKey("research_runs.id"), nullable=False),
        sa.Column("report_json", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_outreach_messages_opportunity_id", "outreach_messages", ["opportunity_id"])


def downgrade():
    op.drop_table("outreach_messages")
