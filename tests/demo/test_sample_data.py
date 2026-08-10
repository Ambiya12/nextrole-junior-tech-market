import csv
import json
from pathlib import Path

from nextrole.demo import generate_sample_dataset


def test_sample_dataset_is_deterministic_and_clearly_disclosed(tmp_path: Path) -> None:
    first = generate_sample_dataset(tmp_path / "first")
    second = generate_sample_dataset(tmp_path / "second")

    assert first.job_count == 84
    assert first.job_skill_count >= first.job_count * 3
    assert (first.output_dir / "jobs.csv").read_bytes() == (
        second.output_dir / "jobs.csv"
    ).read_bytes()
    assert (first.output_dir / "job_skills.csv").read_bytes() == (
        second.output_dir / "job_skills.csv"
    ).read_bytes()

    metadata = json.loads((first.output_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["dataset_kind"] == "synthetic"
    assert "not job-market evidence" in metadata["generated_for"]


def test_sample_dataset_covers_every_role_and_has_valid_skill_relationships(
    tmp_path: Path,
) -> None:
    summary = generate_sample_dataset(tmp_path)

    with (tmp_path / "jobs.csv").open(encoding="utf-8", newline="") as jobs_file:
        jobs = list(csv.DictReader(jobs_file))
    with (tmp_path / "job_skills.csv").open(encoding="utf-8", newline="") as skills_file:
        job_skills = list(csv.DictReader(skills_file))

    job_ids = {job["job_id"] for job in jobs}
    roles = {job["normalized_role"] for job in jobs}
    assert len(roles) == 7
    assert {skill["job_id"] for skill in job_skills}.issubset(job_ids)
    assert len(jobs) == summary.job_count
