"""Opt-in startup probes. Never log exception text, URLs, SQL or application rows."""

import json
import logging
import re

import psycopg
from sqlalchemy import create_engine
from sqlalchemy import exc as sqlalchemy_errors
from sqlalchemy.pool import NullPool

logger = logging.getLogger("opportunityos")

METADATA_SQL = """SELECT
    current_schema() AS current_schema,
    current_setting('search_path') AS search_path,
    to_regclass('profiles') IS NOT NULL AS profiles_resolves,
    to_regclass('alembic_version') IS NOT NULL AS alembic_version_resolves
"""
PROBES = (
    ("profiles", "SELECT profiles.id FROM profiles WHERE FALSE"),
    ("alembic_version", "SELECT version_num FROM alembic_version WHERE FALSE"),
)
SAFE_SCHEMAS = frozenset({"public", "pg_catalog", "information_schema", "auth", "extensions"})
EXCEPTION_NAMES = {
    value: name
    for module in (sqlalchemy_errors, psycopg, psycopg.errors)
    for name, value in vars(module).items()
    if isinstance(value, type) and issubclass(value, Exception)
}
EXCEPTION_NAMES.update({ValueError: "ValueError", RuntimeError: "RuntimeError"})


def _error_fields(exc):
    driver = getattr(exc, "orig", None)
    state = getattr(driver if driver is not None else exc, "sqlstate", None)
    if not isinstance(state, str) or re.fullmatch(r"[0-9A-Z]{5}", state) is None:
        state = None
    return {
        "sqlalchemy_exception_class": EXCEPTION_NAMES.get(type(exc), "Exception"),
        "driver_exception_class": EXCEPTION_NAMES.get(type(driver), "Exception")
        if driver is not None
        else None,
        "sqlstate": state,
    }


def _schema(value):
    return value if isinstance(value, str) and value in SAFE_SCHEMAS else "[redacted]"


def _search_path(value):
    if not isinstance(value, str) or len(value) > 1024:
        return "[redacted]"
    return ", ".join(
        '"$user"' if part.strip() == '"$user"' else _schema(part.strip())
        for part in value.split(",")
    )


def _emit(stage, connection_success, exc=None, **fields):
    record = {
        "diagnostic_stage": stage,
        "connection_success": connection_success,
        "sqlalchemy_exception_class": None,
        "driver_exception_class": None,
        "sqlstate": None,
        "current_schema": None,
        "search_path": None,
        "profiles_resolves": None,
        "profiles_column_probe_success": None,
        "alembic_version_resolves": None,
        "alembic_column_probe_success": None,
    }
    if exc is not None:
        record.update(_error_fields(exc))
    record.update(fields)
    # A logging sink failure is not an application startup failure.
    try:
        logger.warning("%s", json.dumps(record, ensure_ascii=True))
    except Exception:
        return


def _probe(conn, stage, sql):
    try:
        with conn.begin_nested():
            result = conn.exec_driver_sql(sql)
            if stage == "metadata":
                row = result.mappings().one()
                fields = {
                    "current_schema": _schema(row["current_schema"])
                    if row["current_schema"] is not None
                    else None,
                    "search_path": _search_path(row["search_path"]),
                    "profiles_resolves": row["profiles_resolves"] is True,
                    "alembic_version_resolves": row["alembic_version_resolves"] is True,
                }
            else:
                fields = {
                    "profiles_column_probe_success"
                    if stage == "profiles"
                    else "alembic_column_probe_success": True
                }
            result.close()
        _emit(stage, True, **fields)
    except Exception as exc:
        fields = {}
        if stage != "metadata":
            fields[
                "profiles_column_probe_success"
                if stage == "profiles"
                else "alembic_column_probe_success"
            ] = False
        _emit(stage, True, exc, **fields)


def run_postgres_diagnostics(application_engine):
    """Use the existing target/role with a disposable psycopg engine; never commit."""
    temporary_engine = None
    connected = False
    stage = "connection"
    try:
        # No dialect fallback and no changes to the application's engine or session factory.
        if application_engine.url.drivername != "postgresql+psycopg":
            raise ValueError()
        temporary_engine = create_engine(
            application_engine.url,
            poolclass=NullPool,
            pool_pre_ping=True,
            hide_parameters=True,
            echo=False,
            logging_name="avsar_postgres_startup",
            pool_logging_name="avsar_postgres_startup",
            connect_args={"connect_timeout": 5},
        )
        # Dedicated logger names prevent these flags affecting the application engine.
        # SQLAlchemy pool cleanup errors can otherwise emit raw driver tracebacks.
        temporary_engine.logger.disabled = True
        temporary_engine.pool.logger.disabled = True
        with temporary_engine.connect() as conn:
            connected = True
            stage = "read_only_setup"
            transaction = conn.begin()
            try:
                conn.exec_driver_sql("SET TRANSACTION READ ONLY")
                conn.exec_driver_sql("SET LOCAL statement_timeout = '3000ms'")
                conn.exec_driver_sql("SET LOCAL lock_timeout = '1000ms'")
                if conn.exec_driver_sql("SHOW transaction_read_only").scalar_one() != "on":
                    raise RuntimeError()
                _emit("connection", True)
                _probe(conn, "metadata", METADATA_SQL)
                for probe_stage, sql in PROBES:
                    _probe(conn, probe_stage, sql)
            finally:
                try:
                    transaction.rollback()
                except Exception as exc:
                    _emit("rollback", connected, exc)
            stage = "close"
    except Exception as exc:
        _emit(stage, connected, exc)
    finally:
        if temporary_engine is not None:
            try:
                temporary_engine.dispose()
            except Exception as exc:
                _emit("dispose", connected, exc)
