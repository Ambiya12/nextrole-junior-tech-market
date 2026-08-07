import os
from datetime import UTC, datetime, timedelta
from uuid import UUID

import psycopg
import pytest

from nextrole.domain import NormalizedJobPosting, RoleFamily
from nextrole.transformation import ExtractedSkill
from nextrole.warehouse import WarehouseLoader, apply_migrations

DATABASE_URL = os.getenv("NEXTROLE_TEST_DATABASE_URL")
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not DATABASE_URL, reason="NEXTROLE_TEST_DATABASE_URL is not configured"),
]


def test_migrations_and_incremental_replay_against_postgresql() -> None:
    assert DATABASE_URL is not None
    with psycopg.connect(DATABASE_URL, autocommit=True) as connection:
        apply_migrations(connection)
        connection.execute(
            """
            TRUNCATE duplicate_observations, job_skills, rejected_records,
                     job_postings, skills, pipeline_runs
            """
        )

        first_seen = datetime(2026, 8, 7, 12, 0, tzinfo=UTC)
        first_posting = _posting(first_seen, "SQL")
        WarehouseLoader(connection, clock=lambda: first_seen + timedelta(minutes=1)).load(
            run_id=UUID("11111111-1111-1111-1111-111111111111"),
            source="integration_test",
            started_at=first_seen,
            input_count=1,
            postings=[first_posting],
            extracted_skills=[_skill(first_posting, "SQL", 0, 3)],
        )

        second_seen = first_seen + timedelta(days=1)
        updated_posting = _posting(second_seen, "Python and SQL")
        WarehouseLoader(connection, clock=lambda: second_seen + timedelta(minutes=1)).load(
            run_id=UUID("22222222-2222-2222-2222-222222222222"),
            source="integration_test",
            started_at=second_seen,
            input_count=1,
            postings=[updated_posting],
            extracted_skills=[
                _skill(updated_posting, "Python", 0, 6),
                _skill(updated_posting, "SQL", 11, 14),
            ],
        )

        job_count, description, first_seen_at, last_seen_at = connection.execute(
            """
            SELECT COUNT(*) OVER (), description, first_seen_at, last_seen_at
            FROM job_postings
            """
        ).fetchone()
        skill_count = connection.execute("SELECT COUNT(*) FROM job_skills").fetchone()[0]
        successful_runs = connection.execute(
            "SELECT COUNT(*) FROM pipeline_runs WHERE status = 'succeeded'"
        ).fetchone()[0]

    assert job_count == 1
    assert description == "Python and SQL"
    assert first_seen_at == first_seen
    assert last_seen_at == second_seen
    assert skill_count == 2
    assert successful_runs == 2


def _posting(collected_at: datetime, description: str) -> NormalizedJobPosting:
    return NormalizedJobPosting(
        job_id="a" * 64,
        source="integration_test",
        source_job_id="job-1",
        title="Data Analyst Junior",
        description=description,
        source_url="https://example.test/jobs/job-1",
        published_at=datetime(2026, 8, 1, tzinfo=UTC),
        collected_at=collected_at,
        normalized_role=RoleFamily.DATA_ANALYST,
    )


def _skill(posting: NormalizedJobPosting, term: str, start: int, end: int) -> ExtractedSkill:
    slug = term.casefold()
    return ExtractedSkill(
        job_id=posting.job_id,
        skill_slug=slug,
        skill_name=term,
        skill_category="programming_language",
        matched_term=term,
        evidence=posting.description,
        start=start,
        end=end,
        extraction_method="taxonomy_v1_regex",
    )
