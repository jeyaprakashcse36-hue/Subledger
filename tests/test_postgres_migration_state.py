from dataclasses import replace

import pytest

from app.db.session import Base
from app import models as _models  # noqa: F401
from tests.postgres_migration_state import (
    EXPECTED_INDEX_NAMES,
    UnsafeMigrationStateError,
    expected_unversioned_schema,
    validate_unversioned_schema,
)


@pytest.fixture
def expected_schema():
    return expected_unversioned_schema(Base.metadata)


def test_accepts_valid_unversioned_schema(expected_schema):
    validate_unversioned_schema(expected_schema, expected_schema)


def test_rejects_missing_required_index(expected_schema):
    indexes = dict(expected_schema.indexes)
    indexes["invoices"] = {
        name: index
        for name, index in indexes["invoices"].items()
        if name != "uq_invoice_subscription_period"
    }

    with pytest.raises(UnsafeMigrationStateError, match="indexes differ for invoices"):
        validate_unversioned_schema(
            replace(expected_schema, indexes=indexes), expected_schema
        )


def test_rejects_incompatible_column(expected_schema):
    columns = dict(expected_schema.columns)
    customer_columns = list(columns["customers"])
    name_index = next(
        index for index, column in enumerate(customer_columns) if column[0] == "name"
    )
    name_column = customer_columns[name_index]
    customer_columns[name_index] = (
        name_column[0],
        "character varying(151)",
        name_column[2],
        name_column[3],
    )
    columns["customers"] = tuple(customer_columns)

    with pytest.raises(UnsafeMigrationStateError, match="columns differ for customers"):
        validate_unversioned_schema(
            replace(expected_schema, columns=columns), expected_schema
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("triggers", frozenset({"ledger_entries.ledger_entries_append_only"}), "triggers"),
        ("functions", frozenset({"prevent_ledger_entry_mutation"}), "functions"),
    ],
)
def test_rejects_existing_trigger_or_function(expected_schema, field, value, message):
    with pytest.raises(UnsafeMigrationStateError, match=message):
        validate_unversioned_schema(
            replace(expected_schema, **{field: value}), expected_schema
        )


def test_rejects_unexpected_table(expected_schema):
    with pytest.raises(UnsafeMigrationStateError, match="tables expected"):
        validate_unversioned_schema(
            replace(
                expected_schema,
                tables=expected_schema.tables | {"unexpected_table"},
            ),
            expected_schema,
        )


def test_expected_indexes_match_migration_revisions(expected_schema):
    assert {
        table_name: frozenset(indexes)
        for table_name, indexes in expected_schema.indexes.items()
    } == EXPECTED_INDEX_NAMES
    assert "ix_customers_email" not in expected_schema.indexes["customers"]
