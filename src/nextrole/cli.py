"""Command-line entry point for local pipeline operations."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from nextrole import __version__
from nextrole.config import get_settings
from nextrole.demo.sample_data import generate_sample_dataset


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nextrole",
        description="Collect and analyze junior technology job postings.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("config", help="Show the active non-secret configuration")
    demo_parser = subparsers.add_parser(
        "demo-data", help="Generate the deterministic synthetic portfolio dataset"
    )
    demo_parser.add_argument("--output", type=Path, default=Path("data/sample"))
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
        summary = generate_sample_dataset(args.output)
        print(f"jobs={summary.job_count}")
        print(f"job_skills={summary.job_skill_count}")
        print(f"output={summary.output_dir}")
        return 0

    parser.print_help()
    return 0
