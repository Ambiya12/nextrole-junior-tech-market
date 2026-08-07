"""Deterministic duplicate resolution across repeated collection runs."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from nextrole.domain import NormalizedJobPosting


class DuplicateDecision(BaseModel):
    """Audit record explaining why one observed version was not retained."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    job_id: str
    source: str
    source_job_id: str
    discarded_collected_at: datetime
    retained_collected_at: datetime
    reason: str = "same_source_job_id"


class DeduplicationResult(BaseModel):
    """Canonical records and the decisions made to produce them."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    postings: tuple[NormalizedJobPosting, ...]
    duplicates: tuple[DuplicateDecision, ...]
    input_count: int

    @property
    def duplicate_count(self) -> int:
        return len(self.duplicates)


def deduplicate(postings: list[NormalizedJobPosting]) -> DeduplicationResult:
    """Keep the newest, richest observation for each stable source job ID."""

    groups: dict[str, list[NormalizedJobPosting]] = defaultdict(list)
    for posting in postings:
        groups[posting.job_id].append(posting)

    canonical: list[NormalizedJobPosting] = []
    decisions: list[DuplicateDecision] = []

    for job_id in sorted(groups):
        candidates = sorted(groups[job_id], key=_retention_key, reverse=True)
        retained = candidates[0]
        canonical.append(retained)
        decisions.extend(
            DuplicateDecision(
                job_id=discarded.job_id,
                source=discarded.source,
                source_job_id=discarded.source_job_id,
                discarded_collected_at=discarded.collected_at,
                retained_collected_at=retained.collected_at,
            )
            for discarded in candidates[1:]
        )

    return DeduplicationResult(
        postings=tuple(canonical),
        duplicates=tuple(
            sorted(
                decisions,
                key=lambda decision: (
                    decision.job_id,
                    decision.discarded_collected_at,
                ),
            )
        ),
        input_count=len(postings),
    )


def _retention_key(posting: NormalizedJobPosting) -> tuple[object, ...]:
    """Rank observations without depending on their input order."""

    populated_optional_fields = sum(
        value is not None
        for value in (
            posting.company_name,
            posting.city,
            posting.region,
            posting.education_level,
            posting.salary_min,
            posting.salary_max,
            posting.salary_currency,
            posting.salary_period,
            posting.published_at,
        )
    )
    return (
        posting.collected_at,
        populated_optional_fields,
        len(posting.description),
        posting.model_dump_json(),
    )
