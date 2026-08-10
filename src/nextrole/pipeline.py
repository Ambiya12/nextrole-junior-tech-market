"""Orchestration boundary for one collected source batch."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol
from uuid import UUID, uuid4

from nextrole.collection import CollectionBatch, SnapshotStore
from nextrole.domain import NormalizedJobPosting
from nextrole.transformation import (
    DuplicateDecision,
    ExtractedSkill,
    deduplicate,
    extract_skills,
    normalize_posting,
)
from nextrole.warehouse import LoadSummary


class WarehouseSink(Protocol):
    def load(
        self,
        *,
        run_id: UUID,
        source: str,
        started_at: datetime,
        input_count: int,
        postings: tuple[NormalizedJobPosting, ...],
        extracted_skills: tuple[ExtractedSkill, ...],
        duplicates: tuple[DuplicateDecision, ...] = (),
        rejected_count: int = 0,
    ) -> LoadSummary: ...


@dataclass(frozen=True)
class PreparedBatch:
    postings: tuple[NormalizedJobPosting, ...]
    skills: tuple[ExtractedSkill, ...]
    duplicates: tuple[DuplicateDecision, ...]


@dataclass(frozen=True)
class PipelineSummary:
    run_id: UUID
    snapshot_path: Path
    postings_collected: int
    postings_loaded: int
    skills_extracted: int
    duplicates_found: int


def prepare_batch(batch: CollectionBatch) -> PreparedBatch:
    """Normalize, deduplicate, and enrich a valid collected batch."""

    normalized = [normalize_posting(posting) for posting in batch.postings]
    deduplicated = deduplicate(normalized)
    skills = tuple(match for posting in deduplicated.postings for match in extract_skills(posting))
    return PreparedBatch(deduplicated.postings, skills, deduplicated.duplicates)


def execute_batch(
    batch: CollectionBatch,
    *,
    snapshot_store: SnapshotStore,
    warehouse_loader: WarehouseSink,
    run_id: UUID | None = None,
) -> PipelineSummary:
    """Persist raw provenance first, then atomically load canonical warehouse data."""

    active_run_id = run_id or uuid4()
    snapshot_path = snapshot_store.write(
        source=batch.source,
        collection_id=active_run_id,
        collected_at=batch.collected_at,
        query=batch.query.model_dump(mode="json"),
        pages=batch.pages,
    )
    prepared = prepare_batch(batch)
    load_summary = warehouse_loader.load(
        run_id=active_run_id,
        source=batch.source,
        started_at=batch.collected_at,
        input_count=len(batch.postings),
        postings=prepared.postings,
        extracted_skills=prepared.skills,
        duplicates=prepared.duplicates,
    )
    return PipelineSummary(
        run_id=active_run_id,
        snapshot_path=snapshot_path,
        postings_collected=len(batch.postings),
        postings_loaded=load_summary.postings_loaded,
        skills_extracted=load_summary.skills_loaded,
        duplicates_found=load_summary.duplicates_recorded,
    )
