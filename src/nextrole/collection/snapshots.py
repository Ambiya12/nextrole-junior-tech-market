"""Immutable on-disk storage for unmodified source response pages."""

from __future__ import annotations

import json
import os
import re
import tempfile
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

SAFE_SOURCE = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")


class SnapshotStore:
    """Write traceable raw collection batches without allowing replacement."""

    def __init__(self, raw_data_dir: Path) -> None:
        self._raw_data_dir = raw_data_dir

    def write(
        self,
        *,
        source: str,
        collection_id: UUID,
        collected_at: datetime,
        query: Mapping[str, Any],
        pages: Sequence[Mapping[str, Any]],
    ) -> Path:
        if SAFE_SOURCE.fullmatch(source) is None:
            raise ValueError("source must be a lowercase snake_case identifier")
        if collected_at.tzinfo is None or collected_at.utcoffset() is None:
            raise ValueError("collected_at must be timezone-aware")

        utc_timestamp = collected_at.astimezone(UTC)
        directory = self._raw_data_dir / source / utc_timestamp.strftime("%Y/%m/%d")
        directory.mkdir(parents=True, exist_ok=True)
        filename = f"{utc_timestamp.strftime('%Y%m%dT%H%M%SZ')}-{collection_id}.json"
        destination = directory / filename
        payload = {
            "collection_id": str(collection_id),
            "source": source,
            "collected_at": utc_timestamp.isoformat().replace("+00:00", "Z"),
            "query": dict(query),
            "pages": list(pages),
        }

        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=directory,
                prefix=".snapshot-",
                suffix=".tmp",
                delete=False,
            ) as temporary_file:
                json.dump(payload, temporary_file, ensure_ascii=False, separators=(",", ":"))
                temporary_file.write("\n")
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
                temporary_path = Path(temporary_file.name)

            os.link(temporary_path, destination)
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

        return destination
