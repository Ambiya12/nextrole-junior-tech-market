"""Transactional, incremental loading into the NextRole warehouse."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID

from nextrole.domain import NormalizedJobPosting
from nextrole.taxonomy import SkillTaxonomy, load_default_taxonomy
from nextrole.transformation import DuplicateDecision, ExtractedSkill


class CommandResult(Protocol):
    def fetchone(self) -> tuple[Any, ...] | None: ...


class WarehouseConnection(Protocol):
    def execute(
        self,
        query: str,
        params: Mapping[str, object] | Sequence[object] | None = None,
    ) -> CommandResult: ...

    def transaction(self) -> AbstractContextManager[object]: ...


class WarehouseLoadError(ValueError):
    """Raised before loading a batch that violates pipeline invariants."""


@dataclass(frozen=True)
class LoadSummary:
    run_id: UUID
    postings_seen: int
    postings_loaded: int
    skills_loaded: int
    duplicates_recorded: int


class WarehouseLoader:
    """Load one canonical pipeline batch and preserve run-level audit state."""

    def __init__(
        self,
        connection: WarehouseConnection,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._connection = connection
        self._clock = clock or (lambda: datetime.now(UTC))

    def load(
        self,
        *,
        run_id: UUID,
        source: str,
        started_at: datetime,
        input_count: int,
        postings: Sequence[NormalizedJobPosting],
        extracted_skills: Sequence[ExtractedSkill],
        duplicates: Sequence[DuplicateDecision] = (),
        rejected_count: int = 0,
        taxonomy: SkillTaxonomy | None = None,
    ) -> LoadSummary:
        self._validate_batch(input_count, postings, extracted_skills, rejected_count)
        active_taxonomy = taxonomy or load_default_taxonomy()
        matches_by_job: dict[str, list[ExtractedSkill]] = defaultdict(list)
        for match in extracted_skills:
            matches_by_job[match.job_id].append(match)

        self._start_run(run_id, source, started_at, input_count)
        try:
            with self._connection.transaction():
                self._seed_taxonomy(active_taxonomy)
                updated_job_ids = {
                    posting.job_id for posting in postings if self._upsert_posting(posting)
                }
                for job_id in updated_job_ids:
                    self._replace_job_skills(job_id, matches_by_job.get(job_id, []))
                for decision in duplicates:
                    self._record_duplicate(run_id, decision)
                self._finish_run(
                    run_id,
                    self._clock(),
                    loaded_count=len(postings),
                    rejected_count=rejected_count,
                    duplicate_count=len(duplicates),
                )
        except Exception as error:
            self._fail_run(run_id, self._clock(), str(error))
            raise

        return LoadSummary(
            run_id=run_id,
            postings_seen=input_count,
            postings_loaded=len(postings),
            skills_loaded=len(extracted_skills),
            duplicates_recorded=len(duplicates),
        )

    @staticmethod
    def _validate_batch(
        input_count: int,
        postings: Sequence[NormalizedJobPosting],
        extracted_skills: Sequence[ExtractedSkill],
        rejected_count: int,
    ) -> None:
        if input_count < 0 or rejected_count < 0:
            raise WarehouseLoadError("record counts cannot be negative")
        posting_ids = {posting.job_id for posting in postings}
        unknown_job_ids = {match.job_id for match in extracted_skills} - posting_ids
        if unknown_job_ids:
            raise WarehouseLoadError("extracted skills reference jobs outside the batch")
        if len(posting_ids) != len(postings):
            raise WarehouseLoadError("canonical postings contain duplicate job IDs")
        if len(postings) + rejected_count > input_count:
            raise WarehouseLoadError("loaded and rejected counts exceed input count")

    def _start_run(self, run_id: UUID, source: str, started_at: datetime, input_count: int) -> None:
        with self._connection.transaction():
            self._connection.execute(
                """
                INSERT INTO pipeline_runs (
                    run_id, source, status, started_at, records_extracted
                ) VALUES (%s, %s, 'running', %s, %s)
                """,
                (run_id, source, started_at, input_count),
            )

    def _seed_taxonomy(self, taxonomy: SkillTaxonomy) -> None:
        for skill in taxonomy.skills:
            self._connection.execute(
                """
                INSERT INTO skills (skill_slug, skill_name, skill_category, taxonomy_version)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (skill_slug) DO UPDATE SET
                    skill_name = EXCLUDED.skill_name,
                    skill_category = EXCLUDED.skill_category,
                    taxonomy_version = EXCLUDED.taxonomy_version
                """,
                (skill.slug, skill.name, skill.category.value, taxonomy.version),
            )

    def _upsert_posting(self, posting: NormalizedJobPosting) -> bool:
        result = self._connection.execute(
            """
            INSERT INTO job_postings (
                job_id, source, source_job_id, title, normalized_role, company_name,
                location_text, city, region, contract_type, experience_level,
                education_level, salary_min, salary_max, salary_currency, salary_period,
                work_mode, description, published_at, first_seen_at, last_seen_at, source_url
            ) VALUES (
                %(job_id)s, %(source)s, %(source_job_id)s, %(title)s, %(normalized_role)s,
                %(company_name)s, %(location_text)s, %(city)s, %(region)s, %(contract_type)s,
                %(experience_level)s, %(education_level)s, %(salary_min)s, %(salary_max)s,
                %(salary_currency)s, %(salary_period)s, %(work_mode)s, %(description)s,
                %(published_at)s, %(collected_at)s, %(collected_at)s, %(source_url)s
            )
            ON CONFLICT (job_id) DO UPDATE SET
                title = EXCLUDED.title,
                normalized_role = EXCLUDED.normalized_role,
                company_name = EXCLUDED.company_name,
                location_text = EXCLUDED.location_text,
                city = EXCLUDED.city,
                region = EXCLUDED.region,
                contract_type = EXCLUDED.contract_type,
                experience_level = EXCLUDED.experience_level,
                education_level = EXCLUDED.education_level,
                salary_min = EXCLUDED.salary_min,
                salary_max = EXCLUDED.salary_max,
                salary_currency = EXCLUDED.salary_currency,
                salary_period = EXCLUDED.salary_period,
                work_mode = EXCLUDED.work_mode,
                description = EXCLUDED.description,
                published_at = EXCLUDED.published_at,
                first_seen_at = LEAST(job_postings.first_seen_at, EXCLUDED.first_seen_at),
                last_seen_at = EXCLUDED.last_seen_at,
                source_url = EXCLUDED.source_url
            WHERE EXCLUDED.last_seen_at >= job_postings.last_seen_at
            RETURNING job_id
            """,
            {
                "job_id": posting.job_id,
                "source": posting.source,
                "source_job_id": posting.source_job_id,
                "title": posting.title,
                "normalized_role": posting.normalized_role.value,
                "company_name": posting.company_name,
                "location_text": posting.location_text,
                "city": posting.city,
                "region": posting.region,
                "contract_type": posting.contract_type.value,
                "experience_level": posting.experience_level.value,
                "education_level": posting.education_level,
                "salary_min": posting.salary_min,
                "salary_max": posting.salary_max,
                "salary_currency": posting.salary_currency,
                "salary_period": posting.salary_period.value if posting.salary_period else None,
                "work_mode": posting.work_mode.value,
                "description": posting.description,
                "published_at": posting.published_at,
                "collected_at": posting.collected_at,
                "source_url": str(posting.source_url),
            },
        )
        return result.fetchone() is not None

    def _replace_job_skills(self, job_id: str, matches: Sequence[ExtractedSkill]) -> None:
        self._connection.execute("DELETE FROM job_skills WHERE job_id = %s", (job_id,))
        for match in matches:
            self._connection.execute(
                """
                INSERT INTO job_skills (
                    job_id, skill_slug, matched_term, evidence, match_start, match_end,
                    extraction_method
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    match.job_id,
                    match.skill_slug,
                    match.matched_term,
                    match.evidence,
                    match.start,
                    match.end,
                    match.extraction_method,
                ),
            )

    def _record_duplicate(self, run_id: UUID, decision: DuplicateDecision) -> None:
        self._connection.execute(
            """
            INSERT INTO duplicate_observations (
                run_id, job_id, source, source_job_id, discarded_collected_at,
                retained_collected_at, reason
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
            """,
            (
                run_id,
                decision.job_id,
                decision.source,
                decision.source_job_id,
                decision.discarded_collected_at,
                decision.retained_collected_at,
                decision.reason,
            ),
        )

    def _finish_run(
        self,
        run_id: UUID,
        completed_at: datetime,
        *,
        loaded_count: int,
        rejected_count: int,
        duplicate_count: int,
    ) -> None:
        self._connection.execute(
            """
            UPDATE pipeline_runs SET
                status = 'succeeded', completed_at = %s, records_loaded = %s,
                records_rejected = %s, duplicates_found = %s
            WHERE run_id = %s
            """,
            (completed_at, loaded_count, rejected_count, duplicate_count, run_id),
        )

    def _fail_run(self, run_id: UUID, completed_at: datetime, error_message: str) -> None:
        with self._connection.transaction():
            self._connection.execute(
                """
                UPDATE pipeline_runs SET
                    status = 'failed', completed_at = %s, error_message = %s
                WHERE run_id = %s
                """,
                (completed_at, error_message[:2_000], run_id),
            )
