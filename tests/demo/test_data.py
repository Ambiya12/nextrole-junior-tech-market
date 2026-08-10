import csv
import json
from pathlib import Path

import pytest

from nextrole.demo import DemoDataError, load_demo_dataset


def test_load_demo_dataset_validates_generated_files(tmp_path: Path) -> None:
    from nextrole.demo import generate_sample_dataset

    generate_sample_dataset(tmp_path)
    dataset = load_demo_dataset(tmp_path)

    assert len(dataset.jobs) == 84
    assert dataset.metadata["dataset_kind"] == "synthetic"
    assert all(job.skill_slugs for job in dataset.jobs)
    assert {job.dataset_kind for job in dataset.jobs} == {"synthetic"}


def test_load_demo_dataset_rejects_unknown_skill_job(tmp_path: Path) -> None:
    _write_minimal_jobs(tmp_path)
    with (tmp_path / "job_skills.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["job_id", "skill_slug", "skill_name", "skill_category"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "job_id": "missing",
                "skill_slug": "sql",
                "skill_name": "SQL",
                "skill_category": "programming_language",
            }
        )

    with pytest.raises(DemoDataError, match="unknown job ID"):
        load_demo_dataset(tmp_path)


def _write_minimal_jobs(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    with (path / "jobs.csv").open("w", encoding="utf-8", newline="") as file:
        columns = [
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
        ]
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerow(
            {
                "job_id": "job-1",
                "title": "Data Analyst",
                "normalized_role": "data_analyst",
                "company_name": "Example",
                "city": "Paris",
                "region": "Île-de-France",
                "contract_type": "permanent",
                "experience_level": "entry_level",
                "work_mode": "hybrid",
                "date_posted": "2026-08-01",
                "source": "test",
                "dataset_kind": "synthetic",
            }
        )
    (path / "metadata.json").write_text(json.dumps({"dataset_kind": "synthetic"}))
