from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import MetaData
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import Connection
from sqlalchemy.schema import (
    CheckConstraint,
    ForeignKeyConstraint,
    UniqueConstraint,
)


APPLICATION_TABLES = frozenset(
    {
        "customers",
        "plans",
        "subscriptions",
        "invoices",
        "ledger_entries",
        "payment_attempts",
    }
)
EXPECTED_INDEX_NAMES = {
    "customers": frozenset({"ix_customers_id", "uq_customers_email_normalized"}),
    "plans": frozenset({"ix_plans_id"}),
    "subscriptions": frozenset(
        {
            "ix_subscriptions_customer_id",
            "ix_subscriptions_id",
            "ix_subscriptions_plan_id",
            "ix_subscriptions_status",
            "uq_active_customer_plan",
        }
    ),
    "invoices": frozenset(
        {
            "ix_invoices_customer_id",
            "ix_invoices_id",
            "ix_invoices_status",
            "ix_invoices_subscription_id",
            "uq_invoice_subscription_period",
        }
    ),
    "ledger_entries": frozenset(
        {
            "ix_ledger_entries_customer_id",
            "ix_ledger_entries_entry_type",
            "ix_ledger_entries_id",
            "ix_ledger_entries_invoice_id",
            "ix_ledger_entries_reference_id",
        }
    ),
    "payment_attempts": frozenset(
        {
            "ix_payment_attempts_id",
            "ix_payment_attempts_invoice_id",
            "ix_payment_attempts_status",
        }
    ),
}


@dataclass(frozen=True)
class IndexState:
    terms: tuple[str, ...]
    unique: bool
    predicate: str | None = None


@dataclass(frozen=True)
class SchemaState:
    tables: frozenset[str]
    columns: dict[str, tuple[tuple[str, str, bool, str | None], ...]]
    primary_keys: dict[str, tuple[str, ...]]
    foreign_keys: dict[str, frozenset[tuple[tuple[str, ...], str, tuple[str, ...], str | None]]]
    checks: dict[str, frozenset[tuple[str | None, str]]]
    unique_constraints: dict[str, frozenset[tuple[str, ...]]]
    indexes: dict[str, dict[str, IndexState]]
    triggers: frozenset[str] = field(default_factory=frozenset)
    functions: frozenset[str] = field(default_factory=frozenset)


class UnsafeMigrationStateError(RuntimeError):
    pass


def _normalize_sql(value: Any) -> str:
    sql = str(value).lower().replace('"', "")
    sql = re.sub(r"::\s*(text|numeric|character varying|boolean)", "", sql)
    sql = re.sub(r"\s+", "", sql)
    return sql.replace("(", "").replace(")", "")


def _type_name(value: Any, dialect: Any) -> str:
    return value.compile(dialect=dialect).lower()


def expected_unversioned_schema(metadata: MetaData) -> SchemaState:
    dialect = postgresql.dialect()
    columns = {}
    primary_keys = {}
    foreign_keys = {}
    checks = {}
    unique_constraints = {}
    indexes = {}

    for table in metadata.sorted_tables:
        columns[table.name] = tuple(
            (
                column.name,
                _type_name(column.type, dialect),
                column.nullable,
                (
                    "<serial>"
                    if column.primary_key
                    and column.autoincrement in (True, "auto")
                    else _normalize_sql(column.server_default.arg)
                    if column.server_default is not None
                    else None
                ),
            )
            for column in table.columns
        )
        primary_keys[table.name] = tuple(
            column.name for column in table.primary_key.columns
        )
        foreign_keys[table.name] = frozenset(
            (
                tuple(column.name for column in constraint.columns),
                next(iter(constraint.elements)).column.table.name,
                tuple(
                    element.column.name for element in constraint.elements
                ),
                next(iter(constraint.elements)).ondelete,
            )
            for constraint in table.constraints
            if isinstance(constraint, ForeignKeyConstraint)
        )
        checks[table.name] = frozenset(
            (
                constraint.name,
                _normalize_sql(constraint.sqltext),
            )
            for constraint in table.constraints
            if isinstance(constraint, CheckConstraint)
        )
        unique_constraints[table.name] = frozenset(
            tuple(column.name for column in constraint.columns)
            for constraint in table.constraints
            if isinstance(constraint, UniqueConstraint)
        )

        table_indexes = {}
        for index in table.indexes:
            terms = tuple(
                element.name
                if hasattr(element, "name")
                else _normalize_sql(element)
                for element in index.expressions
            )
            predicate = index.dialect_options["postgresql"].get("where")
            table_indexes[index.name] = IndexState(
                terms=terms,
                unique=index.unique,
                predicate=_normalize_sql(predicate) if predicate is not None else None,
            )
        indexes[table.name] = table_indexes

    return SchemaState(
        tables=frozenset(table.name for table in metadata.tables.values()),
        columns=columns,
        primary_keys=primary_keys,
        foreign_keys=foreign_keys,
        checks=checks,
        unique_constraints=unique_constraints,
        indexes=indexes,
    )


def inspect_postgres_schema(connection: Connection) -> SchemaState:
    from sqlalchemy import inspect

    inspector = inspect(connection)
    tables = frozenset(inspector.get_table_names(schema="public"))
    application_tables = tables & APPLICATION_TABLES
    columns = {}
    primary_keys = {}
    foreign_keys = {}
    checks = {}
    unique_constraints = {}
    indexes = {}

    for table_name in application_tables:
        columns[table_name] = tuple(
            (
                column["name"],
                _type_name(column["type"], connection.dialect),
                column["nullable"],
                (
                    "<serial>"
                    if column["name"] == "id"
                    and column["default"]
                    and str(column["default"]).startswith("nextval(")
                    else _normalize_sql(column["default"])
                    if column["default"] is not None
                    else None
                ),
            )
            for column in inspector.get_columns(table_name, schema="public")
        )
        primary_keys[table_name] = tuple(
            inspector.get_pk_constraint(table_name, schema="public").get(
                "constrained_columns"
            )
            or ()
        )
        foreign_keys[table_name] = frozenset(
            (
                tuple(foreign_key["constrained_columns"]),
                foreign_key["referred_table"],
                tuple(foreign_key["referred_columns"]),
                (foreign_key.get("options") or {}).get("ondelete"),
            )
            for foreign_key in inspector.get_foreign_keys(
                table_name, schema="public"
            )
        )
        checks[table_name] = frozenset(
            (
                constraint.get("name"),
                _normalize_sql(constraint["sqltext"]),
            )
            for constraint in inspector.get_check_constraints(
                table_name, schema="public"
            )
        )
        unique_constraints[table_name] = frozenset(
            tuple(constraint["column_names"])
            for constraint in inspector.get_unique_constraints(
                table_name, schema="public"
            )
        )

        table_indexes = {}

        for index in inspector.get_indexes(table_name, schema="public"):
            # PostgreSQL creates a backing index for UNIQUE constraints.
            # These are validated separately through get_unique_constraints().
            # Do not count them as standalone indexes.
            if index.get("duplicates_constraint"):
                continue

            expressions = iter(index.get("expressions") or ())
            terms = tuple(
                _normalize_sql(next(expressions))
                if column is None
                else column
                for column in index["column_names"]
            )

            predicate = (index.get("dialect_options") or {}).get(
                "postgresql_where"
            )

            table_indexes[index["name"]] = IndexState(
                terms=terms,
                unique=index["unique"],
                predicate=(
                    _normalize_sql(predicate)
                    if predicate is not None
                    else None
                ),
            )

        indexes[table_name] = table_indexes

    trigger_rows = connection.exec_driver_sql(
        """
        SELECT c.relname, t.tgname
        FROM pg_trigger AS t
        JOIN pg_class AS c ON c.oid = t.tgrelid
        JOIN pg_namespace AS n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
          AND c.relname = ANY (%(table_names)s)
          AND NOT t.tgisinternal
        """,
        {"table_names": list(APPLICATION_TABLES)},
    ).fetchall()
    triggers = frozenset(f"{table}.{name}" for table, name in trigger_rows)
    function_rows = connection.exec_driver_sql(
        """
        SELECT p.proname
        FROM pg_proc AS p
        JOIN pg_namespace AS n ON n.oid = p.pronamespace
        WHERE n.nspname = 'public'
          AND p.proname = 'prevent_ledger_entry_mutation'
        """
    ).fetchall()

    return SchemaState(
        tables=tables,
        columns=columns,
        primary_keys=primary_keys,
        foreign_keys=foreign_keys,
        checks=checks,
        unique_constraints=unique_constraints,
        indexes=indexes,
        triggers=triggers,
        functions=frozenset(row[0] for row in function_rows),
    )


def validate_unversioned_schema(
    actual: SchemaState,
    expected: SchemaState,
) -> None:
    differences = []
    if actual.tables != expected.tables:
        differences.append(
            f"tables expected {sorted(expected.tables)}, got {sorted(actual.tables)}"
        )

    for attribute in (
        "columns",
        "primary_keys",
        "foreign_keys",
        "checks",
        "unique_constraints",
        "indexes",
    ):
        expected_value = getattr(expected, attribute)
        actual_value = getattr(actual, attribute)
        for table_name in sorted(expected.tables):
            if actual_value.get(table_name) != expected_value.get(table_name):
                differences.append(
                    f"{attribute} differ for {table_name}: "
                    f"expected {expected_value.get(table_name)!r}, "
                    f"got {actual_value.get(table_name)!r}"
                )

    if actual.triggers:
        differences.append(f"unexpected existing triggers: {sorted(actual.triggers)}")
    if actual.functions:
        differences.append(
            f"conflicting existing functions: {sorted(actual.functions)}"
        )
    if differences:
        raise UnsafeMigrationStateError(
            "Refusing to stamp or migrate unversioned database: "
            + "; ".join(differences)
        )
