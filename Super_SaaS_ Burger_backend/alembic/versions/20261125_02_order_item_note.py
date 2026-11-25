"""Store preparation notes per order item."""

import sqlalchemy as sa
from alembic import op

revision = "20261125_02_order_item_note"
down_revision = "20261125_01_order_history_index"
branch_labels = None
depends_on = None


def upgrade():
    if not op.get_context().as_sql:
        columns = sa.inspect(op.get_bind()).get_columns("order_items")
        if any(column["name"] == "note" for column in columns):
            return
    op.add_column("order_items", sa.Column("note", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("order_items", "note")
