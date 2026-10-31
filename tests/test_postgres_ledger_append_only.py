from uuid import uuid4

import pytest
from sqlalchemy import insert, text
from sqlalchemy.exc import DBAPIError

from app.models import Customer, LedgerEntry


def test_ledger_entries_reject_direct_update_and_delete_postgres(
    postgres_test_engine,
):
    marker = uuid4().hex
    with postgres_test_engine.connect() as connection:
        transaction = connection.begin()
        try:
            customer_id = connection.execute(
                insert(Customer)
                .values(name="Append-only test", email=f"{marker}@example.test")
                .returning(Customer.id)
            ).scalar_one()
            entry_id = connection.execute(
                insert(LedgerEntry)
                .values(
                    customer_id=customer_id,
                    entry_type="test",
                    amount="1.00",
                    currency="INR",
                    reference_id=marker,
                )
                .returning(LedgerEntry.id)
            ).scalar_one()

            statements = (
                text("UPDATE ledger_entries SET amount = 2.00 WHERE id = :id"),
                text("DELETE FROM ledger_entries WHERE id = :id"),
            )
            for statement in statements:
                savepoint = connection.begin_nested()
                try:
                    with pytest.raises(DBAPIError) as error:
                        connection.execute(statement, {"id": entry_id})
                    assert getattr(error.value.orig, "sqlstate", None) == "P0001"
                    assert "ledger entries are append-only" in str(
                        error.value.orig
                        ).lower()
                finally:
                    if savepoint.is_active:
                        savepoint.rollback()
        finally:
            transaction.rollback()
