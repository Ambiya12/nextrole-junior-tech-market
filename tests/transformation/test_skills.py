from datetime import UTC, datetime

from nextrole.domain import NormalizedJobPosting, RoleFamily
from nextrole.transformation import extract_skills


def posting(description: str, *, title: str = "Data Engineer Junior") -> NormalizedJobPosting:
    return NormalizedJobPosting(
        job_id="a" * 64,
        source="test_source",
        source_job_id="job-1",
        title=title,
        description=description,
        source_url="https://example.test/jobs/job-1",
        published_at=datetime(2026, 8, 1, tzinfo=UTC),
        collected_at=datetime(2026, 8, 7, tzinfo=UTC),
        normalized_role=RoleFamily.DATA_ENGINEER,
    )


def test_extract_skills_resolves_aliases_to_canonical_skills() -> None:
    matches = extract_skills(
        posting("Vous utiliserez PowerBI, Postgres, PySpark, GCP et Git au quotidien.")
    )

    assert [match.skill_slug for match in matches] == [
        "power_bi",
        "postgresql",
        "spark",
        "gcp",
        "git",
    ]
    assert matches[0].skill_name == "Power BI"
    assert matches[0].matched_term == "PowerBI"
    assert matches[0].extraction_method == "taxonomy_v1_regex"


def test_extract_skills_keeps_one_match_per_canonical_skill() -> None:
    matches = extract_skills(posting("Python, Python 3 et python sont utilisés."))

    assert len(matches) == 1
    assert matches[0].skill_slug == "python"
    assert matches[0].start == len("Data Engineer Junior\n")


def test_extract_skills_does_not_match_terms_inside_other_words() -> None:
    matches = extract_skills(
        posting("Notre stratégie digitale exige de savoir réagir rapidement.", title="Analyste")
    )

    assert matches == ()


def test_single_letter_language_requires_canonical_casing() -> None:
    lower_case = extract_skills(posting("Vous devrez analyser et restituer les résultats."))
    upper_case = extract_skills(posting("Analyse statistique avec R et SQL."))

    assert "r" not in {match.skill_slug for match in lower_case}
    assert {match.skill_slug for match in upper_case} == {"r", "sql"}


def test_extract_skills_can_record_related_overlapping_technologies() -> None:
    matches = extract_skills(posting("Administration de Microsoft SQL Server et requêtes SQL."))

    assert {match.skill_slug for match in matches} == {"sql", "sql_server"}


def test_extract_skills_includes_short_context_without_full_description() -> None:
    description = "A" * 80 + " Docker " + "B" * 80
    match = extract_skills(posting(description))[0]

    assert match.skill_slug == "docker"
    assert match.evidence.startswith("…")
    assert match.evidence.endswith("…")
    assert len(match.evidence) < len(description)
