"""Command-line entry point for local pipeline operations."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

import psycopg
from pydantic import SecretStr

from nextrole import __version__
from nextrole.collection import FranceTravailClient, FranceTravailSearch, SnapshotStore
from nextrole.config import get_settings
from nextrole.demo.sample_data import generate_sample_dataset
from nextrole.pipeline import execute_batch
from nextrole.warehouse import WarehouseLoader, apply_migrations


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nextrole",
        description="Collect and analyze junior technology job postings.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("config", help="Show the active non-secret configuration")
    demo_parser = subparsers.add_parser(
        "demo-data", help="Generate the deterministic synthetic demo dataset"
    )
    demo_parser.add_argument("--output", type=Path, default=Path("data/sample"))
    subparsers.add_parser("migrate", help="Apply pending PostgreSQL migrations")
    collect_parser = subparsers.add_parser(
        "collect", help="Collect and process France Travail job postings"
    )
    collect_parser.add_argument("--keywords", required=True)
    collect_parser.add_argument("--max-results", type=int, default=150)
    collect_parser.add_argument("--page-size", type=int, default=150)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "config":
        settings = get_settings()
        print(f"environment={settings.environment}")
        print(f"data_dir={settings.data_dir}")
        print(f"log_level={settings.log_level}")
        print(f"database_configured={settings.database_url is not None}")
        return 0

    if args.command == "demo-data":
        demo_summary = generate_sample_dataset(args.output)
        print(f"jobs={demo_summary.job_count}")
        print(f"job_skills={demo_summary.job_skill_count}")
        print(f"output={demo_summary.output_dir}")
        return 0

    if args.command == "migrate":
        settings = get_settings()
        database_url = _required_database_url(settings.database_url)
        with psycopg.connect(database_url, autocommit=True) as connection:
            completed = apply_migrations(connection)
        print(f"migrations_applied={len(completed)}")
        return 0

    if args.command == "collect":
        settings = get_settings()
        database_url = _required_database_url(settings.database_url)
        client_id = _required_secret(
            settings.france_travail_client_id, "NEXTROLE_FRANCE_TRAVAIL_CLIENT_ID"
        )
        client_secret = _required_secret(
            settings.france_travail_client_secret,
            "NEXTROLE_FRANCE_TRAVAIL_CLIENT_SECRET",
        )
        search = FranceTravailSearch(
            keywords=args.keywords,
            max_results=args.max_results,
            page_size=args.page_size,
        )
        with (
            FranceTravailClient(client_id, client_secret) as collector,
            psycopg.connect(database_url, autocommit=True) as connection,
        ):
            apply_migrations(connection)
            batch = collector.collect(search)
            pipeline_summary = execute_batch(
                batch,
                snapshot_store=SnapshotStore(settings.data_dir / "raw"),
                warehouse_loader=WarehouseLoader(connection),
            )
        print(f"run_id={pipeline_summary.run_id}")
        print(f"postings_collected={pipeline_summary.postings_collected}")
        print(f"postings_loaded={pipeline_summary.postings_loaded}")
        print(f"skills_extracted={pipeline_summary.skills_extracted}")
        print(f"duplicates_found={pipeline_summary.duplicates_found}")
        print(f"snapshot={pipeline_summary.snapshot_path}")
        return 0

    parser.print_help()
    return 0


def _required_database_url(value: str | None) -> str:
    if not value:
        raise SystemExit("NEXTROLE_DATABASE_URL is required for this command")
    return value


def _required_secret(value: SecretStr | None, variable_name: str) -> str:
    if value is None:
        raise SystemExit(f"{variable_name} is required for this command")
    secret = value.get_secret_value()
    if not secret:
        raise SystemExit(f"{variable_name} is required for this command")
    return str(secret)
