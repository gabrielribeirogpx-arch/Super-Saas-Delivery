"""Create internal plan entitlements only."""
from alembic import op
import sqlalchemy as sa

revision = "20261006_02_plan_entitlements"
down_revision = "20261006_01_plans"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "plan_entitlements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("plan_id", sa.Integer(), sa.ForeignKey("plans.id"), nullable=False),
        sa.Column("feature_code", sa.String(50), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("limit_value", sa.Integer(), nullable=True),
        sa.Column("reset_period", sa.String(20), nullable=True),
        sa.UniqueConstraint("plan_id", "feature_code", name="uq_plan_entitlements_plan_feature"),
        sa.CheckConstraint("limit_value IS NULL OR limit_value >= 0", name="ck_plan_entitlements_limit"),
        sa.CheckConstraint("reset_period IS NULL OR reset_period = 'monthly'", name="ck_plan_entitlements_reset"),
    )


def downgrade():
    op.drop_table("plan_entitlements")
