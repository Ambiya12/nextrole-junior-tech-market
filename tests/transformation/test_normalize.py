from datetime import UTC, datetime

import pytest

from nextrole.domain import (
    ContractType,
    ExperienceLevel,
    RawJobPosting,
    RoleFamily,
    SalaryPeriod,
    WorkMode,
)
from nextrole.transformation.normalize import (
    clean_html,
    normalize_contract,
    normalize_experience,
    normalize_location,
    normalize_posting,
    normalize_role,
    normalize_salary,
    normalize_work_mode,
    stable_job_id,
)


def raw_posting(**overrides: object) -> RawJobPosting:
    data: dict[str, object] = {
        "source": "france_travail",
        "source_job_id": "198ABCD",
        "title": "Data Analyst Junior H/F",
        "description": "<p>Analyse avec <strong>SQL</strong> et Power BI.</p>",
        "source_url": "https://example.test/jobs/198ABCD",
        "company_name": "  Example Analytics  ",
        "location_text": "75 - PARIS 01",
        "published_at": datetime(2026, 8, 1, 9, 30, tzinfo=UTC),
        "collected_at": datetime(2026, 8, 7, 12, 0, tzinfo=UTC),
        "contract_text": "CDI",
        "salary_text": "Annuel de 35000.0 Euros à 42000.0 Euros",
        "remote_text": "Hybride",
    }
    data.update(overrides)
    return RawJobPosting.model_validate(data)


def test_normalize_posting_builds_a_canonical_analytics_record() -> None:
    normalized = normalize_posting(raw_posting())

    assert normalized.job_id == stable_job_id("france_travail", "198ABCD")
    assert normalized.normalized_role is RoleFamily.DATA_ANALYST
    assert normalized.company_name == "Example Analytics"
    assert normalized.description == "Analyse avec SQL et Power BI."
    assert (normalized.city, normalized.region) == ("Paris", "Île-de-France")
    assert normalized.contract_type is ContractType.PERMANENT
    assert normalized.experience_level is ExperienceLevel.ENTRY_LEVEL
    assert normalized.work_mode is WorkMode.HYBRID
    assert normalized.salary_min == 35_000
    assert normalized.salary_max == 42_000
    assert normalized.salary_currency == "EUR"
    assert normalized.salary_period is SalaryPeriod.YEARLY


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Analyste BI", RoleFamily.BI_ANALYST),
        ("Ingénieur Data Junior", RoleFamily.DATA_ENGINEER),
        ("Data Scientist", RoleFamily.DATA_SCIENTIST),
        ("Développeur Full-stack", RoleFamily.FULLSTACK_DEVELOPER),
        ("Développeur Front End", RoleFamily.FRONTEND_DEVELOPER),
        ("Développeur Java", RoleFamily.BACKEND_DEVELOPER),
        ("Product Owner", RoleFamily.OTHER),
    ],
)
def test_normalize_role_handles_french_and_english_titles(title: str, expected: RoleFamily) -> None:
    assert normalize_role(title) is expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Contrat d'apprentissage", ContractType.APPRENTICESHIP),
        ("Stage", ContractType.INTERNSHIP),
        ("CDI", ContractType.PERMANENT),
        ("CDD 12 mois", ContractType.FIXED_TERM),
        ("Freelance", ContractType.FREELANCE),
        (None, ContractType.UNKNOWN),
        ("Intérim", ContractType.OTHER),
    ],
)
def test_normalize_contract_maps_source_labels(value: str | None, expected: ContractType) -> None:
    assert normalize_contract(value) is expected


def test_experience_prioritizes_explicit_senior_requirements() -> None:
    assert (
        normalize_experience("Data Engineer", "Au moins 5 ans d'expérience", ContractType.PERMANENT)
        is ExperienceLevel.EXPERIENCED
    )
    assert (
        normalize_experience("Data Analyst", "Stage de fin d'études", ContractType.INTERNSHIP)
        is ExperienceLevel.INTERNSHIP
    )


@pytest.mark.parametrize(
    ("remote_text", "description", "expected"),
    [
        ("Télétravail ponctuel", "", WorkMode.HYBRID),
        (None, "Poste 100% remote", WorkMode.REMOTE),
        (None, "Travail sur site à Lyon", WorkMode.ON_SITE),
        (None, "Aucune information", WorkMode.UNKNOWN),
    ],
)
def test_normalize_work_mode_uses_source_field_and_description(
    remote_text: str | None, description: str, expected: WorkMode
) -> None:
    assert normalize_work_mode(remote_text, description) is expected


def test_normalize_location_returns_supported_city_and_region() -> None:
    assert normalize_location("69 - LYON 03") == ("Lyon", "Auvergne-Rhône-Alpes")
    assert normalize_location("Lieu non précisé") == (None, None)


def test_normalize_salary_preserves_period_instead_of_mixing_units() -> None:
    salary = normalize_salary("Mensuel de 2 500,50 EUR à 3 000 EUR")

    assert salary.minimum == 2_500.50
    assert salary.maximum == 3_000
    assert salary.currency == "EUR"
    assert salary.period is SalaryPeriod.MONTHLY
    assert normalize_salary(None).minimum is None


def test_clean_html_preserves_readable_word_boundaries() -> None:
    assert clean_html("<p>Python &amp; SQL</p><ul><li>Airflow</li><li>dbt</li></ul>") == (
        "Python & SQL Airflow dbt"
    )


def test_stable_job_id_is_repeatable_and_source_specific() -> None:
    first = stable_job_id("france_travail", "198ABCD")

    assert first == stable_job_id(" FRANCE_TRAVAIL ", "198ABCD")
    assert first != stable_job_id("another_source", "198ABCD")
    assert len(first) == 64
