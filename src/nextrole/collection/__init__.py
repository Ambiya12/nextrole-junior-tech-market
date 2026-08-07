"""Job-source connectors and immutable snapshot storage."""

from nextrole.collection.france_travail import (
    CollectionBatch,
    CollectionError,
    FranceTravailClient,
    FranceTravailSearch,
)
from nextrole.collection.snapshots import SnapshotStore

__all__ = [
    "CollectionBatch",
    "CollectionError",
    "FranceTravailClient",
    "FranceTravailSearch",
    "SnapshotStore",
]
