import asyncio
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import psycopg
import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.pool import NullPool

from app.config import Settings, settings
from app.utils import postgres_diagnostics as diagnostic

SECRET = "private-fixture-value@example.test"


def db_error(driver):
    return ProgrammingError("private SQL " + SECRET, {"token": SECRET}, driver)


@pytest.fixture
def harness(monkeypatch):
    app_engine = SimpleNamespace(
        url=URL.create(
            "postgresql+psycopg",
            username="fixture-role",
            password=SECRET,
            host="fixture-host",
            database="fixture-db",
            query={"sslmode": "require"},
        )
    )
    engine = MagicMock()
    conn = engine.connect.return_value.__enter__.return_value
    metadata = {
        "current_schema": "public",
        "search_path": '"$user", public',
        "profiles_resolves": True,
        "alembic_version_resolves": True,
    }
    failures = {}
    calls = []

    def execute(sql):
        calls.append(sql)
        if sql in failures:
            raise failures[sql]
        result = MagicMock()
        result.scalar_one.return_value = "on"
        result.mappings.return_value.one.return_value = metadata
        return result

    conn.exec_driver_sql.side_effect = execute
    factory = MagicMock(return_value=engine)
    monkeypatch.setattr(diagnostic, "create_engine", factory)
    return SimpleNamespace(
        app=app_engine,
        engine=engine,
        conn=conn,
        factory=factory,
        metadata=metadata,
        failures=failures,
        calls=calls,
    )


def records(caplog):
    return [json.loads(r.getMessage()) for r in caplog.records if r.name == "opportunityos"]


def test_success_is_read_only_and_uses_separate_engine(harness, caplog):
    diagnostic.run_postgres_diagnostics(harness.app)
    harness.factory.assert_called_once_with(
        harness.app.url,
        poolclass=NullPool,
        pool_pre_ping=True,
        hide_parameters=True,
        echo=False,
        logging_name="avsar_postgres_startup",
        pool_logging_name="avsar_postgres_startup",
        connect_args={"connect_timeout": 5},
    )
    assert harness.calls == [
        "SET TRANSACTION READ ONLY",
        "SET LOCAL statement_timeout = '3000ms'",
        "SET LOCAL lock_timeout = '1000ms'",
        "SHOW transaction_read_only",
        diagnostic.METADATA_SQL,
        *[sql for _, sql in diagnostic.PROBES],
    ]
    rows = records(caplog)
    assert [r["diagnostic_stage"] for r in rows] == [
        "connection",
        "metadata",
        "profiles",
        "alembic_version",
    ]
    assert rows[1]["current_schema"] == "public"
    assert rows[1]["search_path"] == '"$user", public'
    assert rows[1]["profiles_resolves"] is True
    assert rows[1]["alembic_version_resolves"] is True
    assert rows[2]["profiles_column_probe_success"] is True
    assert rows[3]["alembic_column_probe_success"] is True
    assert all(r["connection_success"] is True for r in rows)
    harness.conn.begin.return_value.rollback.assert_called_once()
    harness.conn.begin.return_value.commit.assert_not_called()
    harness.conn.commit.assert_not_called()
    assert harness.conn.begin_nested.call_count == 3
    harness.engine.connect.return_value.__exit__.assert_called_once()
    harness.engine.dispose.assert_called_once()
    assert harness.engine.logger.disabled is True
    assert harness.engine.pool.logger.disabled is True
    assert SECRET not in caplog.text
    assert "fixture-host" not in caplog.text
    assert "postgresql" not in caplog.text


@pytest.mark.parametrize("index", [0, 1])
@pytest.mark.parametrize(
    "driver_class,sqlstate",
    [(psycopg.errors.UndefinedTable, "42P01"), (psycopg.errors.UndefinedColumn, "42703")],
)
def test_individual_probe_failure_does_not_skip_other_table(
    harness, caplog, index, driver_class, sqlstate
):
    stage, sql = diagnostic.PROBES[index]
    harness.failures[sql] = db_error(driver_class(SECRET))
    diagnostic.run_postgres_diagnostics(harness.app)
    rows = {r["diagnostic_stage"]: r for r in records(caplog)}
    failed = rows[stage]
    assert failed["sqlstate"] == sqlstate
    assert failed["sqlalchemy_exception_class"] == "ProgrammingError"
    assert failed["driver_exception_class"] == driver_class.__name__
    field = "profiles_column_probe_success" if index == 0 else "alembic_column_probe_success"
    assert failed[field] is False
    other = "alembic_version" if index == 0 else "profiles"
    assert rows[other]["sqlstate"] is None
    # Context-manager exit receives the exception, invoking SQLAlchemy's savepoint rollback.
    exits = harness.conn.begin_nested.return_value.__exit__.call_args_list
    assert any(call.args[0] is ProgrammingError for call in exits)
    harness.conn.begin.return_value.rollback.assert_called_once()
    harness.engine.dispose.assert_called_once()
    assert SECRET not in caplog.text


def test_metadata_failure_is_isolated(harness, caplog):
    harness.failures[diagnostic.METADATA_SQL] = db_error(psycopg.errors.InsufficientPrivilege())
    diagnostic.run_postgres_diagnostics(harness.app)
    rows = records(caplog)
    assert rows[1]["sqlstate"] == "42501"
    assert rows[1]["profiles_resolves"] is None
    assert rows[2]["profiles_column_probe_success"] is True
    assert rows[3]["alembic_column_probe_success"] is True


def test_connection_failure_is_safe_and_disposes(harness, caplog):
    harness.engine.connect.side_effect = OperationalError(
        SECRET,
        {"password": SECRET},
        psycopg.OperationalError(SECRET),
    )
    diagnostic.run_postgres_diagnostics(harness.app)
    (row,) = records(caplog)
    assert row["connection_success"] is False
    assert row["sqlstate"] is None
    assert row["sqlalchemy_exception_class"] == "OperationalError"
    assert row["driver_exception_class"] == "OperationalError"
    assert not harness.calls
    harness.engine.dispose.assert_called_once()
    assert SECRET not in caplog.text


@pytest.mark.parametrize(
    "operation", ["begin", "SET TRANSACTION READ ONLY", "SHOW transaction_read_only"]
)
def test_setup_failures_never_run_probes(harness, caplog, operation):
    failure = db_error(psycopg.errors.ReadOnlySqlTransaction(SECRET))
    if operation == "begin":
        harness.conn.begin.side_effect = failure
    else:
        harness.failures[operation] = failure
    diagnostic.run_postgres_diagnostics(harness.app)
    assert diagnostic.METADATA_SQL not in harness.calls
    assert records(caplog)[0]["diagnostic_stage"] == "read_only_setup"
    assert records(caplog)[0]["sqlstate"] == "25006"
    harness.engine.dispose.assert_called_once()


def test_read_only_confirmation_required(harness, caplog):
    result = MagicMock()
    result.scalar_one.return_value = "off"
    harness.conn.exec_driver_sql.return_value = result
    harness.conn.exec_driver_sql.side_effect = None
    diagnostic.run_postgres_diagnostics(harness.app)
    harness.conn.begin_nested.assert_not_called()
    assert records(caplog)[0]["sqlalchemy_exception_class"] == "RuntimeError"
    harness.conn.begin.return_value.rollback.assert_called_once()


@pytest.mark.parametrize("operation", ["rollback", "close", "dispose"])
def test_cleanup_failures_are_safe(harness, caplog, operation):
    if operation == "rollback":
        harness.conn.begin.return_value.rollback.side_effect = RuntimeError(SECRET)
    elif operation == "close":
        harness.engine.connect.return_value.__exit__.side_effect = RuntimeError(SECRET)
    else:
        harness.engine.dispose.side_effect = RuntimeError(SECRET)
    diagnostic.run_postgres_diagnostics(harness.app)
    assert any(r["diagnostic_stage"] == operation for r in records(caplog))
    harness.engine.dispose.assert_called_once()
    assert SECRET not in caplog.text


def test_schema_and_search_path_redaction(harness, caplog):
    harness.metadata.update(current_schema=SECRET, search_path=f'public, "{SECRET}", pg_catalog')
    diagnostic.run_postgres_diagnostics(harness.app)
    metadata = records(caplog)[1]
    assert metadata["current_schema"] == "[redacted]"
    assert metadata["search_path"] == "public, [redacted], pg_catalog"
    assert SECRET not in caplog.text


def test_untrusted_exception_class_and_sqlstate_redacted(harness, caplog):
    unsafe_class = type("PrivateFixtureClass", (Exception,), {"sqlstate": SECRET})
    harness.engine.connect.side_effect = unsafe_class(SECRET)
    diagnostic.run_postgres_diagnostics(harness.app)
    (row,) = records(caplog)
    assert row["sqlstate"] is None
    assert row["sqlalchemy_exception_class"] == "Exception"
    assert "PrivateFixtureClass" not in caplog.text
    assert SECRET not in caplog.text


def test_no_postgres_fallback_and_no_application_engine_mutation(harness, caplog):
    harness.app.url = URL.create("sqlite", database="fixture.db")
    diagnostic.run_postgres_diagnostics(harness.app)
    harness.factory.assert_not_called()
    assert records(caplog)[0]["connection_success"] is False


def test_logging_failure_cannot_escape(harness, monkeypatch):
    monkeypatch.setattr(diagnostic.logger, "warning", MagicMock(side_effect=RuntimeError(SECRET)))
    diagnostic.run_postgres_diagnostics(harness.app)
    harness.conn.begin.return_value.rollback.assert_called_once()
    harness.engine.dispose.assert_called_once()


def test_flag_defaults_off(monkeypatch):
    monkeypatch.delenv("POSTGRES_STARTUP_DIAGNOSTICS", raising=False)
    assert Settings(_env_file=None).postgres_startup_diagnostics is False


@pytest.mark.parametrize("enabled,raises", [(False, False), (True, False), (True, True)])
def test_startup_disabled_or_failure_still_yields(monkeypatch, enabled, raises):
    import main

    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "postgres_startup_diagnostics", enabled)

    async def enter():
        async with main.lifespan(main.app):
            return "started"

    with patch.object(
        diagnostic,
        "run_postgres_diagnostics",
        side_effect=RuntimeError(SECRET) if raises else None,
    ) as run:
        assert asyncio.run(enter()) == "started"
    assert run.call_count == int(enabled)


def test_readiness_route_is_unchanged(client):
    import main

    with patch.object(main, "Session", side_effect=RuntimeError(SECRET)):
        response = client.get("/ready")
    assert response.status_code == 503
    assert (
        response.json()["detail"] == "Configured persistence or delivery infrastructure unavailable"
    )
    assert SECRET not in response.text


def test_real_sqlalchemy_savepoint_rollback_continues_without_commit():
    # Exercise SQLAlchemy transaction semantics locally, without creating tables or modifying data.
    engine = create_engine("sqlite://")
    try:
        with engine.connect() as conn:
            transaction = conn.begin()
            with pytest.raises(Exception):
                with conn.begin_nested():
                    conn.exec_driver_sql("SELECT missing_fixture_column")
            assert conn.exec_driver_sql("SELECT 1").scalar_one() == 1
            transaction.rollback()
            assert not conn.in_transaction()
    finally:
        engine.dispose()


def test_real_engine_logging_is_isolated(monkeypatch):
    application_engine = create_engine("sqlite://")
    temporary_engine = create_engine(
        "postgresql+psycopg://fixture-role@localhost/fixture-db",
        poolclass=NullPool,
        logging_name="avsar_postgres_startup",
        pool_logging_name="avsar_postgres_startup",
    )
    original_engine_logging = application_engine.logger.disabled
    original_pool_logging = application_engine.pool.logger.disabled
    monkeypatch.setattr(diagnostic, "create_engine", MagicMock(return_value=temporary_engine))
    monkeypatch.setattr(temporary_engine, "connect", MagicMock(side_effect=RuntimeError(SECRET)))
    try:
        diagnostic.run_postgres_diagnostics(SimpleNamespace(url=URL.create("postgresql+psycopg")))
        assert temporary_engine.logger.disabled is True
        assert temporary_engine.pool.logger.disabled is True
        assert application_engine.logger.disabled is original_engine_logging
        assert application_engine.pool.logger.disabled is original_pool_logging
    finally:
        temporary_engine.dispose()
        application_engine.dispose()
