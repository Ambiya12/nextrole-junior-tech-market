from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from nextrole.domain import (
    ContractType,
    ExperienceLevel,
    NormalizedJobPosting,
    RawJobPosting,
    RoleFamily,
    WorkMode,
)


def raw_posting_data() -> dict[str, object]:
    return {
        "source": "france_travail",
        "source_job_id": "123ABC",
        "title": "Data Analyst Junior",
        "description": "Analyse de données avec SQL et Power BI.",
        "source_url": "https://example.test/jobs/123ABC",
        "company_name": "Example SAS",
        "location_text": "Paris 75",
        "published_at": datetime(2026, 8, 1, 9, 30, tzinfo=UTC),
        "collected_at": datetime(2026, 8, 7, 10, 0, tzinfo=UTC),
    }


def test_raw_posting_strips_surrounding_whitespace() -> None:
    data = raw_posting_data()
    data["title"] = "  Data Analyst Junior  "

    posting = RawJobPosting.model_validate(data)

    assert posting.title == "Data Analyst Junior"
    assert posting.payload == {}


def test_raw_posting_rejects_empty_required_text() -> None:
    data = raw_posting_data()
    data["description"] = "   "

    with pytest.raises(ValidationError, match="description"):
        RawJobPosting.model_validate(data)


def test_raw_posting_requires_timezone_aware_datetimes() -> None:
    data = raw_posting_data()
    data["collected_at"] = datetime(2026, 8, 7, 10, 0)

    with pytest.raises(ValidationError, match="collected_at"):
        RawJobPosting.model_validate(data)


def test_raw_posting_rejects_unexpected_source_fields() -> None:
    data = raw_posting_data()
    data["unexpected"] = True

    with pytest.raises(ValidationError, match="unexpected"):
        RawJobPosting.model_validate(data)


def test_normalized_posting_accepts_canonical_categories() -> None:
    posting = NormalizedJobPosting.model_validate(
        raw_posting_data()
        | {
            "job_id": "a" * 64,
            "normalized_role": RoleFamily.DATA_ANALYST,
            "contract_type": ContractType.PERMANENT,
            "experience_level": ExperienceLevel.ENTRY_LEVEL,
            "work_mode": WorkMode.HYBRID,
            "salary_min": 35_000,
            "salary_max": 42_000,
            "salary_currency": "EUR",
        }
    )

    assert posting.normalized_role is RoleFamily.DATA_ANALYST
    assert posting.contract_type is ContractType.PERMANENT
    assert posting.salary_min == 35_000


def test_normalized_posting_rejects_invalid_job_id() -> None:
    data = raw_posting_data() | {
        "job_id": "not-a-sha256-id",
        "normalized_role": RoleFamily.DATA_ENGINEER,
    }

    with pytest.raises(ValidationError, match="job_id"):
        NormalizedJobPosting.model_validate(data)


def test_normalized_posting_rejects_reversed_salary_range() -> None:
    data = raw_posting_data() | {
        "job_id": "b" * 64,
        "normalized_role": RoleFamily.BI_ANALYST,
        "salary_min": 45_000,
        "salary_max": 35_000,
        "salary_currency": "EUR",
    }

    with pytest.raises(ValidationError, match="salary_min cannot be greater"):
        NormalizedJobPosting.model_validate(data)
