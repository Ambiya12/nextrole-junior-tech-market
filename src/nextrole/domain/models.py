"""Validated contracts for raw and normalized job postings."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any, Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, HttpUrl, model_validator

NonEmptyText = Annotated[str, Field(min_length=1)]
OptionalText = Annotated[str | None, Field(min_length=1)]


class RoleFamily(StrEnum):
    DATA_ANALYST = "data_analyst"
    BI_ANALYST = "bi_analyst"
    DATA_ENGINEER = "data_engineer"
    DATA_SCIENTIST = "data_scientist"
    FRONTEND_DEVELOPER = "frontend_developer"
    BACKEND_DEVELOPER = "backend_developer"
    FULLSTACK_DEVELOPER = "fullstack_developer"
    OTHER = "other"


class ContractType(StrEnum):
    APPRENTICESHIP = "apprenticeship"
    INTERNSHIP = "internship"
    PERMANENT = "permanent"
    FIXED_TERM = "fixed_term"
    FREELANCE = "freelance"
    OTHER = "other"
    UNKNOWN = "unknown"


class ExperienceLevel(StrEnum):
    INTERNSHIP = "internship"
    ENTRY_LEVEL = "entry_level"
    EXPERIENCED = "experienced"
    UNKNOWN = "unknown"


class WorkMode(StrEnum):
    REMOTE = "remote"
    HYBRID = "hybrid"
    ON_SITE = "on_site"
    UNKNOWN = "unknown"


class JobPostingBase(BaseModel):
    """Fields and validation rules shared across pipeline stages."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    source: NonEmptyText
    source_job_id: NonEmptyText
    title: NonEmptyText
    description: NonEmptyText
    source_url: HttpUrl
    company_name: OptionalText = None
    location_text: OptionalText = None
    published_at: AwareDatetime | None = None
    collected_at: AwareDatetime


class RawJobPosting(JobPostingBase):
    """Source-aligned posting before business normalization."""

    contract_text: OptionalText = None
    salary_text: OptionalText = None
    remote_text: OptionalText = None
    payload: dict[str, Any] = Field(default_factory=dict)


class NormalizedJobPosting(JobPostingBase):
    """Canonical posting ready for deduplication and warehouse loading."""

    job_id: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    normalized_role: RoleFamily
    city: OptionalText = None
    region: OptionalText = None
    contract_type: ContractType = ContractType.UNKNOWN
    experience_level: ExperienceLevel = ExperienceLevel.UNKNOWN
    work_mode: WorkMode = WorkMode.UNKNOWN
    education_level: OptionalText = None
    salary_min: Annotated[float | None, Field(ge=0)] = None
    salary_max: Annotated[float | None, Field(ge=0)] = None
    salary_currency: Annotated[str | None, Field(pattern=r"^[A-Z]{3}$")] = None

    @model_validator(mode="after")
    def salary_range_is_ordered(self) -> Self:
        if (
            self.salary_min is not None
            and self.salary_max is not None
            and self.salary_min > self.salary_max
        ):
            raise ValueError("salary_min cannot be greater than salary_max")
        return self
