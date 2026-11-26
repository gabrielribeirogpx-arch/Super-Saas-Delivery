"""Persist each store's roll width for its order tickets."""

import sqlalchemy as sa
from alembic import op

revision = "20261126_01_ticket_paper_width"
down_revision = "20261125_02_order_item_note"
branch_labels = None
depends_on = None


def upgrade():
    if not op.get_context().as_sql:
        columns = sa.inspect(op.get_bind()).get_columns("tenants")
        if any(column["name"] == "ticket_paper_width_mm" for column in columns):
            return
    op.add_column(
        "tenants",
        sa.Column("ticket_paper_width_mm", sa.Integer(), server_default="80", nullable=False),
    )


def downgrade():
    op.drop_column("tenants", "ticket_paper_width_mm")
