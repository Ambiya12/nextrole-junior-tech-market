import os
from datetime import UTC, datetime
from uuid import UUID

import psycopg
import pytest

from nextrole.domain import NormalizedJobPosting, RoleFamily, WorkMode
from nextrole.transformation import ExtractedSkill
from nextrole.warehouse import WarehouseLoader, apply_migrations

DATABASE_URL = os.getenv("NEXTROLE_TEST_DATABASE_URL")
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not DATABASE_URL, reason="NEXTROLE_TEST_DATABASE_URL is not configured"),
]


def test_analytics_views_return_known_kpis() -> None:
    assert DATABASE_URL is not None
    with psycopg.connect(DATABASE_URL, autocommit=True) as connection:
        apply_migrations(connection)
        connection.execute(
            """
            TRUNCATE duplicate_observations, job_skills, rejected_records,
                     job_postings, skills, pipeline_runs
            """
        )

        analyst = _posting("a", RoleFamily.DATA_ANALYST, "Paris", WorkMode.HYBRID)
        engineer = _posting("b", RoleFamily.DATA_ENGINEER, "Lyon", WorkMode.REMOTE)
        matches = [
            _skill(analyst, "sql", "SQL", 0),
            _skill(analyst, "power_bi", "Power BI", 8),
            _skill(engineer, "sql", "SQL", 0),
        ]
        WarehouseLoader(connection).load(
            run_id=UUID("33333333-3333-3333-3333-333333333333"),
            source="analytics_test",
            started_at=datetime(2026, 8, 7, tzinfo=UTC),
            input_count=2,
            postings=[analyst, engineer],
            extracted_skills=matches,
        )

        overview = connection.execute(
            "SELECT total_postings, unique_companies, unique_cities FROM analytics_market_overview"
        ).fetchone()
        sql_demand = connection.execute(
            "SELECT posting_count, posting_percentage FROM analytics_skill_demand "
            "WHERE skill_slug = 'sql'"
        ).fetchone()
        transferability = connection.execute(
            "SELECT role_count FROM analytics_skill_transferability WHERE skill_slug = 'sql'"
        ).fetchone()[0]
        skill_pair_count = connection.execute(
            "SELECT posting_count FROM analytics_skill_pairs "
            "WHERE first_skill_slug = 'power_bi' AND second_skill_slug = 'sql'"
        ).fetchone()[0]

    assert overview == (2, 2, 2)
    assert sql_demand == (2, 100.0)
    assert transferability == 2
    assert skill_pair_count == 1


def _posting(
    identity: str, role: RoleFamily, city: str, work_mode: WorkMode
) -> NormalizedJobPosting:
    return NormalizedJobPosting(
        job_id=identity * 64,
        source="analytics_test",
        source_job_id=f"job-{identity}",
        title=role.value,
        description="SQL and Power BI",
        source_url=f"https://example.test/jobs/{identity}",
        company_name=f"Company {identity.upper()}",
        city=city,
        published_at=datetime(2026, 8, 1, tzinfo=UTC),
        collected_at=datetime(2026, 8, 7, tzinfo=UTC),
        normalized_role=role,
        work_mode=work_mode,
    )


def _skill(posting: NormalizedJobPosting, slug: str, name: str, start: int) -> ExtractedSkill:
    return ExtractedSkill(
        job_id=posting.job_id,
        skill_slug=slug,
        skill_name=name,
        skill_category="programming_language" if slug == "sql" else "bi_tool",
        matched_term=name,
        evidence=posting.description,
        start=start,
        end=start + len(name),
        extraction_method="taxonomy_v1_regex",
    )
