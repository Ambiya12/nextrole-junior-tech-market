"""Small checksum-verified PostgreSQL migration runner."""

from __future__ import annotations

import hashlib
import re
from contextlib import AbstractContextManager
from dataclasses import dataclass
from importlib.resources import files
from typing import Any, Protocol

MIGRATION_NAME = re.compile(r"^(\d{3})_[a-z0-9_]+\.sql$")
MIGRATION_LOCK_ID = 1_384_480_307


class QueryResult(Protocol):
    def fetchall(self) -> list[tuple[Any, ...]]: ...


class SqlConnection(Protocol):
    def execute(self, query: str, params: tuple[object, ...] | None = None) -> QueryResult: ...

    def transaction(self) -> AbstractContextManager[object]: ...


class MigrationError(RuntimeError):
    """Raised when migration history is inconsistent or cannot be trusted."""


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    checksum: str
    sql: str


def load_migrations() -> tuple[Migration, ...]:
    """Load ordered SQL resources and reject ambiguous versions."""

    directory = files("nextrole.warehouse").joinpath("migrations")
    migrations: list[Migration] = []
    versions: set[int] = set()

    for resource in sorted(directory.iterdir(), key=lambda item: item.name):
        match = MIGRATION_NAME.fullmatch(resource.name)
        if match is None:
            continue
        version = int(match.group(1))
        if version in versions:
            raise MigrationError(f"duplicate migration version: {version}")
        versions.add(version)
        sql = resource.read_text(encoding="utf-8")
        migrations.append(
            Migration(
                version=version,
                name=resource.name,
                checksum=hashlib.sha256(sql.encode("utf-8")).hexdigest(),
                sql=sql,
            )
        )

    if not migrations:
        raise MigrationError("no warehouse migrations were found")
    return tuple(migrations)


def apply_migrations(connection: SqlConnection) -> tuple[Migration, ...]:
    """Apply pending migrations transactionally and verify applied checksums."""

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            checksum CHAR(64) NOT NULL,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    applied_rows = connection.execute(
        "SELECT version, checksum FROM schema_migrations ORDER BY version"
    ).fetchall()
    applied = {int(row[0]): str(row[1]) for row in applied_rows}
    completed: list[Migration] = []

    for migration in load_migrations():
        existing_checksum = applied.get(migration.version)
        if existing_checksum is not None:
            if existing_checksum != migration.checksum:
                raise MigrationError(
                    f"migration {migration.version} checksum differs from applied history"
                )
            continue

        with connection.transaction():
            connection.execute("SELECT pg_advisory_xact_lock(%s)", (MIGRATION_LOCK_ID,))
            connection.execute(migration.sql)
            connection.execute(
                "INSERT INTO schema_migrations (version, name, checksum) VALUES (%s, %s, %s)",
                (migration.version, migration.name, migration.checksum),
            )
        completed.append(migration)

    return tuple(completed)
