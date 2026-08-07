"""Deterministic technical-skill extraction with auditable evidence."""

from __future__ import annotations

import re
from functools import lru_cache

from pydantic import BaseModel, ConfigDict, Field

from nextrole.domain import NormalizedJobPosting
from nextrole.taxonomy import SkillCategory, SkillDefinition, SkillTaxonomy, load_default_taxonomy


class ExtractedSkill(BaseModel):
    """One canonical skill found in a job posting."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    job_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    skill_slug: str = Field(pattern=r"^[a-z0-9]+(?:_[a-z0-9]+)*$")
    skill_name: str
    skill_category: SkillCategory
    matched_term: str
    evidence: str
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    extraction_method: str = Field(pattern=r"^taxonomy_v\d+_regex$")


def extract_skills(
    posting: NormalizedJobPosting,
    taxonomy: SkillTaxonomy | None = None,
) -> tuple[ExtractedSkill, ...]:
    """Extract at most one auditable match for each canonical skill."""

    active_taxonomy = taxonomy or load_default_taxonomy()
    searchable = f"{posting.title}\n{posting.description}"
    matches: list[ExtractedSkill] = []

    for skill in active_taxonomy.skills:
        match = _first_skill_match(searchable, skill)
        if match is None:
            continue
        matches.append(
            ExtractedSkill(
                job_id=posting.job_id,
                skill_slug=skill.slug,
                skill_name=skill.name,
                skill_category=skill.category,
                matched_term=match.group(0),
                evidence=_evidence_window(searchable, match.start(), match.end()),
                start=match.start(),
                end=match.end(),
                extraction_method=f"taxonomy_v{active_taxonomy.version}_regex",
            )
        )

    return tuple(sorted(matches, key=lambda skill: (skill.start, skill.skill_slug)))


def _first_skill_match(text: str, skill: SkillDefinition) -> re.Match[str] | None:
    matches = (
        match
        for term in sorted(skill.terms, key=len, reverse=True)
        if (match := _compiled_term(term).search(text)) is not None
    )
    return min(matches, key=lambda match: match.start(), default=None)


@lru_cache(maxsize=512)
def _compiled_term(term: str) -> re.Pattern[str]:
    """Compile a term with token boundaries that avoid matches inside product names."""

    escaped = re.escape(term).replace(r"\ ", r"\s+")
    boundary = rf"(?<![\w+#]){escaped}(?![\w+#])"

    # Single-letter languages are meaningful only with their canonical casing.
    flags = 0 if len(term) == 1 and term.isalpha() else re.IGNORECASE
    return re.compile(boundary, flags)


def _evidence_window(text: str, start: int, end: int, context: int = 45) -> str:
    evidence_start = max(0, start - context)
    evidence_end = min(len(text), end + context)
    evidence = " ".join(text[evidence_start:evidence_end].split())
    if evidence_start > 0:
        evidence = f"…{evidence}"
    if evidence_end < len(text):
        evidence = f"{evidence}…"
    return evidence
