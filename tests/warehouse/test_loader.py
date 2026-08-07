from __future__ import annotations

from contextlib import nullcontext
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest

from nextrole.domain import NormalizedJobPosting, RoleFamily
from nextrole.transformation import ExtractedSkill
from nextrole.warehouse import WarehouseLoader, WarehouseLoadError

RUN_ID = UUID("12345678-1234-5678-1234-567812345678")
STARTED_AT = datetime(2026, 8, 7, 12, 0, tzinfo=UTC)
COMPLETED_AT = datetime(2026, 8, 7, 12, 1, tzinfo=UTC)


class FakeResult:
    def __init__(self, row: tuple[Any, ...] | None = None) -> None:
        self._row = row

    def fetchone(self) -> tuple[Any, ...] | None:
        return self._row


class FakeConnection:
    def __init__(self, *, return_upserted_job: bool = True, fail_on_job: bool = False) -> None:
        self.return_upserted_job = return_upserted_job
        self.fail_on_job = fail_on_job
        self.executed: list[tuple[str, dict[str, object] | tuple[object, ...] | None]] = []

    def execute(
        self,
        query: str,
        params: dict[str, object] | tuple[object, ...] | None = None,
    ) -> FakeResult:
        compact_query = " ".join(query.split())
        self.executed.append((compact_query, params))
        if "INSERT INTO job_postings" in query:
            if self.fail_on_job:
                raise RuntimeError("database unavailable")
            return FakeResult(("a" * 64,)) if self.return_upserted_job else FakeResult()
        return FakeResult()

    def transaction(self) -> nullcontext[None]:
        return nullcontext()


def posting() -> NormalizedJobPosting:
    return NormalizedJobPosting(
        job_id="a" * 64,
        source="france_travail",
        source_job_id="198ABCD",
        title="Data Analyst Junior",
        description="SQL et Power BI",
        source_url="https://example.test/jobs/198ABCD",
        company_name="Example SAS",
        published_at=datetime(2026, 8, 1, tzinfo=UTC),
        collected_at=STARTED_AT,
        normalized_role=RoleFamily.DATA_ANALYST,
    )


def skill() -> ExtractedSkill:
    return ExtractedSkill(
        job_id="a" * 64,
        skill_slug="sql",
        skill_name="SQL",
        skill_category="programming_language",
        matched_term="SQL",
        evidence="SQL et Power BI",
        start=0,
        end=3,
        extraction_method="taxonomy_v1_regex",
    )


def test_loader_upserts_posting_replaces_skills_and_completes_audit_run() -> None:
    connection = FakeConnection()
    loader = WarehouseLoader(connection, clock=lambda: COMPLETED_AT)

    summary = loader.load(
        run_id=RUN_ID,
        source="france_travail",
        started_at=STARTED_AT,
        input_count=1,
        postings=[posting()],
        extracted_skills=[skill()],
    )

    statements = [query for query, _ in connection.executed]
    assert summary.postings_seen == 1
    assert summary.postings_loaded == 1
    assert summary.skills_loaded == 1
    assert any("INSERT INTO pipeline_runs" in query for query in statements)
    assert any("INSERT INTO skills" in query for query in statements)
    assert any("INSERT INTO job_postings" in query for query in statements)
    assert any("DELETE FROM job_skills" in query for query in statements)
    assert any("INSERT INTO job_skills" in query for query in statements)
    assert any("status = 'succeeded'" in query for query in statements)


def test_loader_does_not_replace_skills_when_an_older_posting_loses_upsert() -> None:
    connection = FakeConnection(return_upserted_job=False)
    loader = WarehouseLoader(connection, clock=lambda: COMPLETED_AT)

    loader.load(
        run_id=RUN_ID,
        source="france_travail",
        started_at=STARTED_AT,
        input_count=1,
        postings=[posting()],
        extracted_skills=[skill()],
    )

    statements = [query for query, _ in connection.executed]
    assert not any("DELETE FROM job_skills" in query for query in statements)


def test_loader_rejects_skill_matches_outside_the_batch() -> None:
    unknown_skill = skill().model_copy(update={"job_id": "b" * 64})

    with pytest.raises(WarehouseLoadError, match="outside the batch"):
        WarehouseLoader(FakeConnection()).load(
            run_id=RUN_ID,
            source="france_travail",
            started_at=STARTED_AT,
            input_count=1,
            postings=[posting()],
            extracted_skills=[unknown_skill],
        )


def test_loader_records_failed_run_when_data_transaction_raises() -> None:
    connection = FakeConnection(fail_on_job=True)
    loader = WarehouseLoader(connection, clock=lambda: COMPLETED_AT)

    with pytest.raises(RuntimeError, match="database unavailable"):
        loader.load(
            run_id=RUN_ID,
            source="france_travail",
            started_at=STARTED_AT,
            input_count=1,
            postings=[posting()],
            extracted_skills=[],
        )

    statements = [query for query, _ in connection.executed]
    assert any("status = 'failed'" in query for query in statements)


@pytest.mark.parametrize(
    ("input_count", "postings", "rejected_count", "message"),
    [
        (-1, [], 0, "cannot be negative"),
        (1, [posting(), posting()], 0, "duplicate job IDs"),
        (1, [posting()], 1, "exceed input count"),
    ],
)
def test_loader_rejects_inconsistent_batch_counts(
    input_count: int,
    postings: list[NormalizedJobPosting],
    rejected_count: int,
    message: str,
) -> None:
    with pytest.raises(WarehouseLoadError, match=message):
        WarehouseLoader(FakeConnection()).load(
            run_id=RUN_ID,
            source="france_travail",
            started_at=STARTED_AT,
            input_count=input_count,
            postings=postings,
            extracted_skills=[],
            rejected_count=rejected_count,
        )
