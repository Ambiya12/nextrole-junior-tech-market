from datetime import UTC, datetime

from nextrole.domain import NormalizedJobPosting, RoleFamily
from nextrole.transformation import deduplicate


def posting(
    job_id: str,
    *,
    collected_at: datetime,
    description: str = "SQL",
    company_name: str | None = None,
) -> NormalizedJobPosting:
    return NormalizedJobPosting(
        job_id=job_id * 64,
        source="france_travail",
        source_job_id=f"source-{job_id}",
        title="Data Analyst Junior",
        description=description,
        source_url=f"https://example.test/jobs/{job_id}",
        company_name=company_name,
        published_at=datetime(2026, 8, 1, tzinfo=UTC),
        collected_at=collected_at,
        normalized_role=RoleFamily.DATA_ANALYST,
    )


def test_deduplicate_keeps_latest_observation_and_audits_the_discarded_one() -> None:
    older = posting("a", collected_at=datetime(2026, 8, 7, tzinfo=UTC))
    newer = posting(
        "a",
        collected_at=datetime(2026, 8, 8, tzinfo=UTC),
        description="SQL and Power BI",
    )

    result = deduplicate([older, newer])

    assert result.input_count == 2
    assert result.postings == (newer,)
    assert result.duplicate_count == 1
    assert result.duplicates[0].discarded_collected_at == older.collected_at
    assert result.duplicates[0].retained_collected_at == newer.collected_at
    assert result.duplicates[0].reason == "same_source_job_id"


def test_deduplicate_prefers_richer_record_when_collection_time_is_equal() -> None:
    collected_at = datetime(2026, 8, 7, tzinfo=UTC)
    sparse = posting("b", collected_at=collected_at)
    richer = posting("b", collected_at=collected_at, company_name="Example SAS")

    result = deduplicate([richer, sparse])

    assert result.postings == (richer,)


def test_deduplicate_output_does_not_depend_on_input_order() -> None:
    collected_at = datetime(2026, 8, 7, tzinfo=UTC)
    first = posting("c", collected_at=collected_at)
    second = posting("d", collected_at=collected_at)

    forward = deduplicate([second, first])
    reverse = deduplicate([first, second])

    assert forward == reverse
    assert [item.job_id for item in forward.postings] == ["c" * 64, "d" * 64]


def test_deduplicate_handles_empty_batches() -> None:
    result = deduplicate([])

    assert result.input_count == 0
    assert result.postings == ()
    assert result.duplicates == ()
