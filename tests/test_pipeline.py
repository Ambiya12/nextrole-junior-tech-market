from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

from nextrole.collection import CollectionBatch, FranceTravailSearch, SnapshotStore
from nextrole.domain import NormalizedJobPosting, RawJobPosting
from nextrole.pipeline import execute_batch, prepare_batch
from nextrole.transformation import DuplicateDecision, ExtractedSkill
from nextrole.warehouse import LoadSummary

RUN_ID = UUID("12345678-1234-5678-1234-567812345678")
COLLECTED_AT = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)


class RecordingLoader:
    def __init__(self) -> None:
        self.arguments: dict[str, object] = {}

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
    ) -> LoadSummary:
        self.arguments = {
            "run_id": run_id,
            "source": source,
            "started_at": started_at,
            "input_count": input_count,
            "postings": postings,
            "extracted_skills": extracted_skills,
            "duplicates": duplicates,
            "rejected_count": rejected_count,
        }
        return LoadSummary(
            run_id=run_id,
            postings_seen=input_count,
            postings_loaded=len(postings),
            skills_loaded=len(extracted_skills),
            duplicates_recorded=len(duplicates),
        )


def raw_posting(collected_at: datetime, description: str) -> RawJobPosting:
    return RawJobPosting(
        source="france_travail",
        source_job_id="job-1",
        title="Data Analyst Junior",
        description=description,
        source_url="https://example.test/jobs/job-1",
        company_name="Example SAS",
        location_text="75 - PARIS 01",
        published_at=datetime(2026, 8, 1, tzinfo=UTC),
        collected_at=collected_at,
        contract_text="CDI",
        remote_text="Hybride",
    )


def collection_batch() -> CollectionBatch:
    return CollectionBatch(
        source="france_travail",
        collected_at=COLLECTED_AT,
        query=FranceTravailSearch(keywords="data", max_results=2, page_size=2),
        pages=({"resultats": [{"id": "job-1"}]},),
        postings=(
            raw_posting(COLLECTED_AT - timedelta(days=1), "SQL"),
            raw_posting(COLLECTED_AT, "SQL et Power BI"),
        ),
    )


def test_prepare_batch_keeps_latest_duplicate_and_extracts_its_skills() -> None:
    prepared = prepare_batch(collection_batch())

    assert len(prepared.postings) == 1
    assert prepared.postings[0].description == "SQL et Power BI"
    assert {match.skill_slug for match in prepared.skills} == {"sql", "power_bi"}
    assert len(prepared.duplicates) == 1


def test_execute_batch_snapshots_before_loading_and_reconciles_counts(tmp_path: Path) -> None:
    loader = RecordingLoader()

    summary = execute_batch(
        collection_batch(),
        snapshot_store=SnapshotStore(tmp_path / "raw"),
        warehouse_loader=loader,
        run_id=RUN_ID,
    )

    assert summary.run_id == RUN_ID
    assert summary.snapshot_path.exists()
    assert summary.postings_collected == 2
    assert summary.postings_loaded == 1
    assert summary.skills_extracted == 2
    assert summary.duplicates_found == 1
    assert loader.arguments["input_count"] == 2
