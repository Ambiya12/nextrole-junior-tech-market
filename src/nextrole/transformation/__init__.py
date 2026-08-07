"""Deterministic transformations from source records to canonical postings."""

from nextrole.transformation.deduplicate import DeduplicationResult, DuplicateDecision, deduplicate
from nextrole.transformation.normalize import normalize_posting
from nextrole.transformation.skills import ExtractedSkill, extract_skills

__all__ = [
    "DeduplicationResult",
    "DuplicateDecision",
    "ExtractedSkill",
    "deduplicate",
    "extract_skills",
    "normalize_posting",
]
