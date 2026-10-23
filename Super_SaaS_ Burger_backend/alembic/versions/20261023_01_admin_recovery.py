"""Administrative password recovery version and durable resend cooldown."""
from alembic import op
import sqlalchemy as sa
revision = '20261023_01_admin_recovery'
down_revision = '20261019_01_hotmart'
branch_labels = None
depends_on = None

def upgrade():
    columns = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('admin_users')}
    if 'credential_version' not in columns:
        op.add_column('admin_users', sa.Column('credential_version', sa.Integer(), nullable=False, server_default='0'))
    if 'recovery_sent_at' not in columns:
        op.add_column('admin_users', sa.Column('recovery_sent_at', sa.DateTime(), nullable=True))

def downgrade():
    op.drop_column('admin_users', 'recovery_sent_at')
    op.drop_column('admin_users', 'credential_version')
