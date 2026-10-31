from argparse import Namespace
from collections.abc import Iterator
from pathlib import Path
import os

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.db.session import Base, get_db
from app.main import app
from app import models as _models  # noqa: F401
from tests.postgres_migration_state import (
    UnsafeMigrationStateError,
    expected_unversioned_schema,
    inspect_postgres_schema,
    validate_unversioned_schema,
)


@pytest.fixture(scope="session")
def postgres_test_engine():
    test_database_url = os.getenv("TEST_DATABASE_URL")
    if not test_database_url:
        pytest.skip("Set TEST_DATABASE_URL to run PostgreSQL integration coverage")

    test_url = make_url(test_database_url)
    if test_url.get_backend_name() != "postgresql":
        pytest.fail("TEST_DATABASE_URL must use PostgreSQL")
    if not test_url.database or not test_url.database.endswith("_test"):
        pytest.fail("TEST_DATABASE_URL must point to a dedicated database ending in _test")

    development_url = make_url(settings.database_url)
    if test_url.database == development_url.database:
        pytest.fail("TEST_DATABASE_URL must not point to the development database")

    alembic_config = Config(str(Path(__file__).resolve().parent.parent / "alembic.ini"))
    migration_args = [f"database_url={test_database_url}"]
    alembic_config.cmd_opts = Namespace(x=migration_args)
    expected_schema = expected_unversioned_schema(Base.metadata)

    inspection_engine = create_engine(test_database_url, pool_pre_ping=True)
    try:
        with inspection_engine.connect() as connection:
            table_names = set(inspect(connection).get_table_names(schema="public"))
            if "alembic_version" not in table_names:
                state = inspect_postgres_schema(connection)
                try:
                    validate_unversioned_schema(state, expected_schema)
                except UnsafeMigrationStateError as error:
                    pytest.fail(str(error))
                command.stamp(alembic_config, "5954c11189c1")
            else:
                revisions = set(
                    connection.execute(
                        text("SELECT version_num FROM public.alembic_version")
                    ).scalars()
                )
                if revisions not in (
                    {"5954c11189c1"},
                    {"20261030_integrity"},
                ):
                    pytest.fail(
                        f"Refusing to migrate database with unknown Alembic revisions: "
                        f"{sorted(revisions)}"
                    )
        command.upgrade(alembic_config, "head")
    finally:
        inspection_engine.dispose()

    engine = create_engine(test_database_url, pool_pre_ping=True)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def test_engine():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, connection_record) -> None:
        dbapi_connection.isolation_level = None
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    @event.listens_for(engine, "begin")
    def begin_sqlite_transaction(connection) -> None:
        connection.exec_driver_sql("BEGIN")

    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db_session(test_engine) -> Iterator[Session]:
    testing_session = sessionmaker(
        bind=test_engine, autoflush=False, expire_on_commit=False
    )
    with testing_session() as session:
        yield session


@pytest.fixture
def client(test_engine) -> Iterator[TestClient]:
    testing_session = sessionmaker(
        bind=test_engine, autoflush=False, expire_on_commit=False
    )

    def override_get_db():
        with testing_session() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def customer(client: TestClient) -> dict:
    response = client.post(
        "/api/v1/customers",
        json={"name": "Ada Lovelace", "email": "Ada@example.com"},
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture
def plan(client: TestClient) -> dict:
    response = client.post(
        "/api/v1/plans",
        json={
            "name": "Standard",
            "price": "100.00",
            "currency": "INR",
            "billing_interval": "monthly",
        },
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture
def subscription(client: TestClient, customer: dict, plan: dict) -> dict:
    response = client.post(
        "/api/v1/subscriptions",
        json={
            "customer_id": customer["id"],
            "plan_id": plan["id"],
            "current_period_start": "2026-01-01T00:00:00Z",
            "current_period_end": "2026-02-01T00:00:00Z",
        },
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture
def invoice(client: TestClient, subscription: dict) -> dict:
    response = client.post(
        "/api/v1/invoices",
        json={
            "subscription_id": subscription["id"],
            "period_start": "2026-01-01",
            "period_end": "2026-02-01",
        },
    )
    assert response.status_code == 201
    return response.json()
