"""Validated loading for the credential-free portfolio dataset."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

JOB_COLUMNS = {
    "job_id",
    "title",
    "normalized_role",
    "company_name",
    "city",
    "region",
    "contract_type",
    "experience_level",
    "work_mode",
    "date_posted",
    "source",
    "dataset_kind",
}
SKILL_COLUMNS = {"job_id", "skill_slug", "skill_name", "skill_category"}


class DemoDataError(ValueError):
    """Raised when publishable demo files violate their data contract."""


@dataclass(frozen=True)
class DemoJob:
    job_id: str
    title: str
    role: str
    company: str
    city: str
    region: str
    contract_type: str
    experience_level: str
    work_mode: str
    date_posted: date
    source: str
    dataset_kind: str
    skill_slugs: frozenset[str]


@dataclass(frozen=True)
class DemoDataset:
    jobs: tuple[DemoJob, ...]
    skill_names: dict[str, str]
    skill_categories: dict[str, str]
    metadata: dict[str, object]


def load_demo_dataset(data_dir: Path) -> DemoDataset:
    """Load sample CSV files and enforce uniqueness and relationships."""

    jobs_path = data_dir / "jobs.csv"
    skills_path = data_dir / "job_skills.csv"
    metadata_path = data_dir / "metadata.json"
    job_rows = _read_csv(jobs_path, JOB_COLUMNS)
    skill_rows = _read_csv(skills_path, SKILL_COLUMNS)
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if not isinstance(metadata, dict):
        raise DemoDataError("metadata.json must contain an object")

    job_ids = [row["job_id"] for row in job_rows]
    if len(job_ids) != len(set(job_ids)):
        raise DemoDataError("jobs.csv contains duplicate job IDs")

    known_job_ids = set(job_ids)
    skills_by_job: dict[str, set[str]] = {job_id: set() for job_id in job_ids}
    skill_names: dict[str, str] = {}
    skill_categories: dict[str, str] = {}
    for row in skill_rows:
        job_id = row["job_id"]
        if job_id not in known_job_ids:
            raise DemoDataError(f"job skill references unknown job ID: {job_id}")
        slug = row["skill_slug"]
        known_name = skill_names.setdefault(slug, row["skill_name"])
        known_category = skill_categories.setdefault(slug, row["skill_category"])
        if known_name != row["skill_name"] or known_category != row["skill_category"]:
            raise DemoDataError(f"inconsistent skill definition: {slug}")
        skills_by_job[job_id].add(slug)

    jobs = tuple(
        DemoJob(
            job_id=row["job_id"],
            title=row["title"],
            role=row["normalized_role"],
            company=row["company_name"],
            city=row["city"],
            region=row["region"],
            contract_type=row["contract_type"],
            experience_level=row["experience_level"],
            work_mode=row["work_mode"],
            date_posted=date.fromisoformat(row["date_posted"]),
            source=row["source"],
            dataset_kind=row["dataset_kind"],
            skill_slugs=frozenset(skills_by_job[row["job_id"]]),
        )
        for row in job_rows
    )
    if not jobs:
        raise DemoDataError("the demo dataset contains no jobs")
    if any(not job.skill_slugs for job in jobs):
        raise DemoDataError("every demo job must have at least one skill")
    if {job.dataset_kind for job in jobs} != {"synthetic"}:
        raise DemoDataError("portfolio demo jobs must be explicitly marked synthetic")

    return DemoDataset(jobs, skill_names, skill_categories, metadata)


def _read_csv(path: Path, expected_columns: set[str]) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        if set(reader.fieldnames or ()) != expected_columns:
            raise DemoDataError(f"unexpected columns in {path.name}")
        return [dict(row) for row in reader]
