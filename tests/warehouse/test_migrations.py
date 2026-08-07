from __future__ import annotations

from contextlib import nullcontext
from typing import Any

import pytest

from nextrole.warehouse import MigrationError, apply_migrations, load_migrations


class FakeResult:
    def __init__(self, rows: list[tuple[Any, ...]] | None = None) -> None:
        self._rows = rows or []

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self._rows


class FakeConnection:
    def __init__(self, applied: list[tuple[Any, ...]] | None = None) -> None:
        self.applied = applied or []
        self.executed: list[tuple[str, tuple[object, ...] | None]] = []

    def execute(self, query: str, params: tuple[object, ...] | None = None) -> FakeResult:
        self.executed.append((query, params))
        if query.startswith("SELECT version"):
            return FakeResult(self.applied)
        return FakeResult()

    def transaction(self) -> nullcontext[None]:
        return nullcontext()


def test_bundled_migration_defines_constrained_warehouse_tables() -> None:
    migration = load_migrations()[0]

    assert migration.version == 1
    assert migration.name == "001_create_core_schema.sql"
    assert len(migration.checksum) == 64
    for table in (
        "pipeline_runs",
        "job_postings",
        "skills",
        "job_skills",
        "duplicate_observations",
        "rejected_records",
    ):
        assert f"CREATE TABLE {table}" in migration.sql


def test_apply_migrations_records_pending_migration_and_uses_advisory_lock() -> None:
    connection = FakeConnection()

    completed = apply_migrations(connection)

    assert completed == load_migrations()
    statements = [statement for statement, _ in connection.executed]
    assert any("CREATE TABLE IF NOT EXISTS schema_migrations" in sql for sql in statements)
    assert any("pg_advisory_xact_lock" in sql for sql in statements)
    assert any("INSERT INTO schema_migrations" in sql for sql in statements)


def test_apply_migrations_is_a_noop_for_matching_history() -> None:
    migration = load_migrations()[0]
    connection = FakeConnection([(migration.version, migration.checksum)])

    assert apply_migrations(connection) == ()
    assert not any("pg_advisory_xact_lock" in sql for sql, _ in connection.executed)


def test_apply_migrations_rejects_changed_applied_sql() -> None:
    migration = load_migrations()[0]
    connection = FakeConnection([(migration.version, "0" * 64)])

    with pytest.raises(MigrationError, match="checksum differs"):
        apply_migrations(connection)
