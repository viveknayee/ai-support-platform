"""enable_row_level_security

Revision ID: 4330d52b4676
Revises: 196b1a1214f0
Create Date: 2026-07-29 16:06:51.221100

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4330d52b4676'
down_revision: Union[str, Sequence[str], None] = '196b1a1214f0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TABLE users ENABLE ROW LEVEL SECURITY;")

    op.execute("""
        CREATE OR REPLACE FUNCTION current_tenant_id()
        RETURNS UUID AS $$
            SELECT current_setting('app.current_tenant_id', true)::UUID;
        $$ LANGUAGE SQL STABLE;
    """)

    op.execute("""
        CREATE POLICY tenant_isolation_policy ON users
        FOR ALL
        USING (tenant_id = current_tenant_id());
    """)



def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON users;")
    op.execute("DROP FUNCTION IF EXISTS current_tenant_id();")
    op.execute("ALTER TABLE users DISABLE ROW LEVEL SECURITY;")
