"""Generate a deterministic and explicitly synthetic dashboard dataset."""

from __future__ import annotations

import csv
import hashlib
import json
import random
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from nextrole.domain import RoleFamily
from nextrole.taxonomy import SkillTaxonomy, load_default_taxonomy

DATASET_SEED = 20_260_807
JOBS_PER_ROLE = 12

ROLE_SKILLS: dict[RoleFamily, tuple[str, ...]] = {
    RoleFamily.DATA_ANALYST: ("sql", "excel", "power_bi", "python", "tableau", "azure", "git"),
    RoleFamily.BI_ANALYST: ("sql", "power_bi", "excel", "tableau", "qlik", "azure", "agile"),
    RoleFamily.DATA_ENGINEER: (
        "python",
        "sql",
        "spark",
        "airflow",
        "dbt",
        "docker",
        "aws",
        "azure",
        "kafka",
        "databricks",
    ),
    RoleFamily.DATA_SCIENTIST: ("python", "sql", "r", "spark", "databricks", "aws", "git"),
    RoleFamily.FRONTEND_DEVELOPER: (
        "javascript",
        "typescript",
        "react",
        "angular",
        "vue",
        "git",
        "docker",
    ),
    RoleFamily.BACKEND_DEVELOPER: (
        "java",
        "python",
        "spring_boot",
        "django",
        "fastapi",
        "postgresql",
        "docker",
        "git",
    ),
    RoleFamily.FULLSTACK_DEVELOPER: (
        "javascript",
        "typescript",
        "react",
        "node_js",
        "postgresql",
        "docker",
        "git",
    ),
}

ROLE_TITLES: dict[RoleFamily, tuple[str, ...]] = {
    RoleFamily.DATA_ANALYST: ("Data Analyst Junior", "Analyste Data", "Junior Data Analyst"),
    RoleFamily.BI_ANALYST: ("BI Analyst Junior", "Analyste BI", "Consultant BI Junior"),
    RoleFamily.DATA_ENGINEER: ("Data Engineer Junior", "Ingénieur Data", "Junior Data Engineer"),
    RoleFamily.DATA_SCIENTIST: ("Data Scientist Junior", "Junior Data Scientist"),
    RoleFamily.FRONTEND_DEVELOPER: ("Développeur Frontend Junior", "Junior Frontend Developer"),
    RoleFamily.BACKEND_DEVELOPER: ("Développeur Backend Junior", "Junior Backend Developer"),
    RoleFamily.FULLSTACK_DEVELOPER: ("Développeur Full-Stack Junior", "Junior Fullstack Developer"),
}

CITIES: tuple[tuple[str, str], ...] = (
    ("Paris", "Île-de-France"),
    ("Lyon", "Auvergne-Rhône-Alpes"),
    ("Lille", "Hauts-de-France"),
    ("Toulouse", "Occitanie"),
    ("Bordeaux", "Nouvelle-Aquitaine"),
    ("Nantes", "Pays de la Loire"),
    ("Rennes", "Bretagne"),
)

COMPANIES = (
    "Aster Data",
    "BluePeak Systems",
    "Cobalt Digital",
    "Hexa Metrics",
    "Juniper Labs",
    "Northstar Tech",
    "Orion Services",
    "Riverstone Software",
    "Solstice Analytics",
    "Vertex Cloud",
)

CONTRACTS = ("permanent", "permanent", "apprenticeship", "internship", "fixed_term")
WORK_MODES = ("hybrid", "hybrid", "on_site", "remote")


@dataclass(frozen=True)
class SampleDatasetSummary:
    output_dir: Path
    job_count: int
    job_skill_count: int


def generate_sample_dataset(output_dir: Path) -> SampleDatasetSummary:
    """Regenerate the same publishable demo files on every machine."""

    taxonomy = load_default_taxonomy()
    rng = random.Random(DATASET_SEED)
    output_dir.mkdir(parents=True, exist_ok=True)

    jobs: list[dict[str, str]] = []
    job_skills: list[dict[str, str]] = []
    base_date = date(2026, 5, 1)

    for role_index, (role, available_skills) in enumerate(ROLE_SKILLS.items()):
        for role_job_index in range(JOBS_PER_ROLE):
            sequence = role_index * JOBS_PER_ROLE + role_job_index
            job_id = hashlib.sha256(f"synthetic-demo:{sequence}".encode()).hexdigest()
            city, region = CITIES[(sequence * 3 + role_index) % len(CITIES)]
            contract = CONTRACTS[(sequence + role_index) % len(CONTRACTS)]
            work_mode = WORK_MODES[(sequence * 2 + role_index) % len(WORK_MODES)]
            selected_skill_count = 3 + (sequence % min(4, len(available_skills) - 2))
            selected_skills = rng.sample(list(available_skills), selected_skill_count)

            jobs.append(
                {
                    "job_id": job_id,
                    "title": ROLE_TITLES[role][role_job_index % len(ROLE_TITLES[role])],
                    "normalized_role": role.value,
                    "company_name": COMPANIES[(sequence * 5 + role_index) % len(COMPANIES)],
                    "city": city,
                    "region": region,
                    "contract_type": contract,
                    "experience_level": (
                        "internship" if contract == "internship" else "entry_level"
                    ),
                    "work_mode": work_mode,
                    "date_posted": (base_date + timedelta(days=(sequence * 7) % 92)).isoformat(),
                    "source": "synthetic_demo",
                    "dataset_kind": "synthetic",
                }
            )
            job_skills.extend(
                _skill_row(job_id, skill_slug, taxonomy) for skill_slug in selected_skills
            )

    _write_csv(output_dir / "jobs.csv", jobs)
    _write_csv(output_dir / "job_skills.csv", job_skills)
    metadata = {
        "dataset_kind": "synthetic",
        "source": "NextRole deterministic demo generator",
        "seed": DATASET_SEED,
        "job_count": len(jobs),
        "job_skill_count": len(job_skills),
        "generated_for": "Interface demonstration only; not job-market evidence",
    }
    (output_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return SampleDatasetSummary(output_dir, len(jobs), len(job_skills))


def _skill_row(job_id: str, skill_slug: str, taxonomy: SkillTaxonomy) -> dict[str, str]:
    skill = next(skill for skill in taxonomy.skills if skill.slug == skill_slug)
    return {
        "job_id": job_id,
        "skill_slug": skill.slug,
        "skill_name": skill.name,
        "skill_category": skill.category.value,
    }


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        raise ValueError("sample dataset tables cannot be empty")
    with path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
