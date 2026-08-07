import json
from datetime import UTC, datetime
from uuid import UUID

import pytest

from nextrole.collection import SnapshotStore


def test_snapshot_store_writes_traceable_immutable_json(tmp_path: object) -> None:
    root = tmp_path / "raw"  # type: ignore[operator]
    store = SnapshotStore(root)
    collection_id = UUID("12345678-1234-5678-1234-567812345678")
    collected_at = datetime(2026, 8, 7, 15, 30, tzinfo=UTC)

    destination = store.write(
        source="france_travail",
        collection_id=collection_id,
        collected_at=collected_at,
        query={"keywords": "data", "max_results": 2},
        pages=[{"resultats": [{"id": "198ABCD"}]}],
    )

    assert destination.relative_to(root).as_posix().startswith("france_travail/2026/08/07/")
    payload = json.loads(destination.read_text(encoding="utf-8"))
    assert payload["collection_id"] == str(collection_id)
    assert payload["collected_at"] == "2026-08-07T15:30:00Z"
    assert payload["pages"][0]["resultats"][0]["id"] == "198ABCD"

    with pytest.raises(FileExistsError):
        store.write(
            source="france_travail",
            collection_id=collection_id,
            collected_at=collected_at,
            query={"keywords": "changed"},
            pages=[],
        )


def test_snapshot_store_rejects_unsafe_source_names(tmp_path: object) -> None:
    store = SnapshotStore(tmp_path)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="snake_case"):
        store.write(
            source="../unsafe",
            collection_id=UUID("12345678-1234-5678-1234-567812345678"),
            collected_at=datetime.now(UTC),
            query={},
            pages=[],
        )
