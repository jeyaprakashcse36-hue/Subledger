"""Add invoice period uniqueness and protect ledger rows.

Revision ID: 20261030_integrity
Revises: 5954c11189c1
Create Date: 2026-10-30
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261030_integrity"
down_revision: Union[str, Sequence[str], None] = "5954c11189c1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_customers_email")
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_customers_email_normalized
        ON customers (lower(email))
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_invoice_subscription_period
        ON invoices (subscription_id, period_start, period_end)
        """
    )

    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            """
            CREATE FUNCTION prevent_ledger_entry_mutation()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
                RAISE EXCEPTION 'ledger entries are append-only';
            END;
            $$;
            """
        )
        op.execute(
            """
            CREATE TRIGGER ledger_entries_append_only
            BEFORE UPDATE OR DELETE ON ledger_entries
            FOR EACH ROW EXECUTE FUNCTION prevent_ledger_entry_mutation();
            """
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER ledger_entries_append_only ON ledger_entries")
        op.execute("DROP FUNCTION prevent_ledger_entry_mutation()")

    op.drop_index("uq_invoice_subscription_period", table_name="invoices")
    op.drop_index("uq_customers_email_normalized", table_name="customers")
    op.create_index(
        "ix_customers_email", "customers", ["email"], unique=True
    )
