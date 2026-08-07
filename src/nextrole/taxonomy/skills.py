"""Models and loading helpers for the versioned skills taxonomy."""

from __future__ import annotations

import json
from enum import StrEnum
from functools import cached_property, lru_cache
from importlib.resources import files
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SkillCategory(StrEnum):
    PROGRAMMING_LANGUAGE = "programming_language"
    DATABASE = "database"
    BI_TOOL = "bi_tool"
    CLOUD = "cloud"
    FRAMEWORK = "framework"
    DATA_ENGINEERING = "data_engineering"
    DEVOPS = "devops"
    VERSION_CONTROL = "version_control"
    PRODUCTIVITY = "productivity"
    METHODOLOGY = "methodology"


class SkillDefinition(BaseModel):
    """One canonical skill and the source terms mapped to it."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    slug: str = Field(pattern=r"^[a-z0-9]+(?:_[a-z0-9]+)*$")
    name: str = Field(min_length=1)
    category: SkillCategory
    aliases: tuple[str, ...] = ()

    @property
    def terms(self) -> tuple[str, ...]:
        return (self.name, *self.aliases)


class SkillTaxonomy(BaseModel):
    """An immutable, internally consistent taxonomy release."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    version: int = Field(ge=1)
    skills: tuple[SkillDefinition, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def entries_are_unique(self) -> Self:
        slugs: set[str] = set()
        terms: dict[str, str] = {}

        for skill in self.skills:
            if skill.slug in slugs:
                raise ValueError(f"duplicate skill slug: {skill.slug}")
            slugs.add(skill.slug)

            for term in skill.terms:
                normalized = normalize_term(term)
                existing_slug = terms.get(normalized)
                if existing_slug is not None:
                    raise ValueError(
                        f"term {term!r} is shared by {existing_slug!r} and {skill.slug!r}"
                    )
                terms[normalized] = skill.slug

        return self

    @cached_property
    def by_term(self) -> dict[str, SkillDefinition]:
        return {normalize_term(term): skill for skill in self.skills for term in skill.terms}

    def resolve(self, term: str) -> SkillDefinition | None:
        """Resolve a canonical name or alias without case or spacing sensitivity."""

        return self.by_term.get(normalize_term(term))


def normalize_term(term: str) -> str:
    """Normalize taxonomy terms for exact alias resolution."""

    return " ".join(term.casefold().split())


@lru_cache
def load_default_taxonomy() -> SkillTaxonomy:
    """Load the taxonomy release bundled with the installed package."""

    taxonomy_path = files("nextrole.taxonomy").joinpath("skills.v1.json")
    return SkillTaxonomy.model_validate(json.loads(taxonomy_path.read_text(encoding="utf-8")))
