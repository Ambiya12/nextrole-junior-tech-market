"""Business rules for canonical job-posting fields."""

from __future__ import annotations

import hashlib
import html
import re
import unicodedata
from dataclasses import dataclass
from html.parser import HTMLParser

from nextrole.domain import (
    ContractType,
    ExperienceLevel,
    NormalizedJobPosting,
    RawJobPosting,
    RoleFamily,
    SalaryPeriod,
    WorkMode,
)

SPACE = re.compile(r"\s+")
NUMBER = re.compile(r"(?<!\w)(\d+(?:[\s.,]\d{3})*(?:[.,]\d+)?)(?!\w)")

ROLE_RULES: tuple[tuple[RoleFamily, tuple[str, ...]], ...] = (
    (RoleFamily.BI_ANALYST, (r"\bbi analyst\b", r"\banalyste bi\b", r"business intelligence")),
    (
        RoleFamily.DATA_ENGINEER,
        (r"\bdata engineer\b", r"\bingenieur data\b", r"\bdata engineering\b"),
    ),
    (RoleFamily.DATA_SCIENTIST, (r"\bdata scientist\b", r"\bscientifique des donnees\b")),
    (
        RoleFamily.DATA_ANALYST,
        (r"\bdata analyst\b", r"\banalyste data\b", r"\banalyste de donnees\b"),
    ),
    (
        RoleFamily.FULLSTACK_DEVELOPER,
        (r"\bfull[ -]?stack\b", r"\bdeveloppeur full[ -]?stack\b"),
    ),
    (
        RoleFamily.FRONTEND_DEVELOPER,
        (r"\bfront[ -]?end\b", r"\bdeveloppeur front\b", r"\bintegrateur web\b"),
    ),
    (
        RoleFamily.BACKEND_DEVELOPER,
        (r"\bback[ -]?end\b", r"\bdeveloppeur back\b", r"\bdeveloppeur java\b"),
    ),
)

CITY_REGIONS: tuple[tuple[str, str], ...] = (
    ("Paris", "Île-de-France"),
    ("Lyon", "Auvergne-Rhône-Alpes"),
    ("Lille", "Hauts-de-France"),
    ("Toulouse", "Occitanie"),
    ("Bordeaux", "Nouvelle-Aquitaine"),
    ("Nantes", "Pays de la Loire"),
    ("Marseille", "Provence-Alpes-Côte d'Azur"),
    ("Montpellier", "Occitanie"),
    ("Rennes", "Bretagne"),
    ("Strasbourg", "Grand Est"),
)


@dataclass(frozen=True)
class Salary:
    minimum: float | None
    maximum: float | None
    currency: str | None
    period: SalaryPeriod | None


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"br", "li", "p", "div"}:
            self.parts.append(" ")


def normalize_posting(posting: RawJobPosting) -> NormalizedJobPosting:
    """Convert one valid source record into the canonical analytics contract."""

    clean_description = clean_html(posting.description)
    normalized_role = normalize_role(posting.title)
    contract_type = normalize_contract(posting.contract_text)
    salary = normalize_salary(posting.salary_text)
    city, region = normalize_location(posting.location_text)

    return NormalizedJobPosting(
        job_id=stable_job_id(posting.source, posting.source_job_id),
        source=posting.source,
        source_job_id=posting.source_job_id,
        title=clean_text(posting.title),
        description=clean_description,
        source_url=posting.source_url,
        company_name=clean_optional_text(posting.company_name),
        location_text=clean_optional_text(posting.location_text),
        published_at=posting.published_at,
        collected_at=posting.collected_at,
        normalized_role=normalized_role,
        city=city,
        region=region,
        contract_type=contract_type,
        experience_level=normalize_experience(posting.title, clean_description, contract_type),
        work_mode=normalize_work_mode(posting.remote_text, clean_description),
        salary_min=salary.minimum,
        salary_max=salary.maximum,
        salary_currency=salary.currency,
        salary_period=salary.period,
    )


def stable_job_id(source: str, source_job_id: str) -> str:
    identity = f"{source.strip().casefold()}:{source_job_id.strip()}"
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def clean_text(value: str) -> str:
    return SPACE.sub(" ", html.unescape(value)).strip()


def clean_optional_text(value: str | None) -> str | None:
    return clean_text(value) if value else None


def clean_html(value: str) -> str:
    extractor = _TextExtractor()
    extractor.feed(value)
    extractor.close()
    return clean_text(" ".join(extractor.parts))


def searchable_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    without_accents = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    return SPACE.sub(" ", without_accents.casefold()).strip()


def normalize_role(title: str) -> RoleFamily:
    normalized_title = searchable_text(title)
    for role, patterns in ROLE_RULES:
        if any(re.search(pattern, normalized_title) for pattern in patterns):
            return role
    return RoleFamily.OTHER


def normalize_contract(value: str | None) -> ContractType:
    normalized = searchable_text(value or "")
    if any(term in normalized for term in ("apprentissage", "alternance", "professionnalisation")):
        return ContractType.APPRENTICESHIP
    if any(term in normalized for term in ("stage", "stagiaire", "internship")):
        return ContractType.INTERNSHIP
    if re.search(r"\bcdi\b|contrat a duree indeterminee|permanent", normalized):
        return ContractType.PERMANENT
    if re.search(r"\bcdd\b|contrat a duree determinee|fixed[ -]term", normalized):
        return ContractType.FIXED_TERM
    if any(term in normalized for term in ("freelance", "independant", "independent")):
        return ContractType.FREELANCE
    return ContractType.UNKNOWN if not normalized else ContractType.OTHER


def normalize_experience(
    title: str, description: str, contract_type: ContractType
) -> ExperienceLevel:
    if contract_type is ContractType.INTERNSHIP:
        return ExperienceLevel.INTERNSHIP

    normalized = searchable_text(f"{title} {description}")
    if re.search(r"\b(senior|confirme|experimente|lead)\b", normalized):
        return ExperienceLevel.EXPERIENCED
    if re.search(r"\b[3-9]\s*(?:ans?|annees?|years?)\b", normalized):
        return ExperienceLevel.EXPERIENCED
    if contract_type is ContractType.APPRENTICESHIP or re.search(
        r"\b(junior|debutant|graduate|entry[ -]level)\b", normalized
    ):
        return ExperienceLevel.ENTRY_LEVEL
    if re.search(r"\b(?:0|1|2)\s*(?:ans?|annees?|years?)\b", normalized):
        return ExperienceLevel.ENTRY_LEVEL
    return ExperienceLevel.UNKNOWN


def normalize_work_mode(value: str | None, description: str) -> WorkMode:
    normalized = searchable_text(f"{value or ''} {description}")
    if any(
        term in normalized
        for term in ("hybride", "hybrid", "teletravail partiel", "teletravail ponctuel")
    ):
        return WorkMode.HYBRID
    if any(
        term in normalized
        for term in ("full remote", "100% remote", "teletravail total", "a distance")
    ):
        return WorkMode.REMOTE
    if any(term in normalized for term in ("sur site", "on-site", "onsite", "presentiel")):
        return WorkMode.ON_SITE
    return WorkMode.UNKNOWN


def normalize_location(value: str | None) -> tuple[str | None, str | None]:
    normalized = searchable_text(value or "")
    for city, region in CITY_REGIONS:
        if re.search(rf"\b{re.escape(searchable_text(city))}\b", normalized):
            return city, region
    return None, None


def normalize_salary(value: str | None) -> Salary:
    normalized = searchable_text(value or "")
    numbers = [_parse_number(match) for match in NUMBER.findall(normalized)]
    numbers = [number for number in numbers if number is not None]

    if not numbers:
        return Salary(None, None, None, None)

    period: SalaryPeriod | None = SalaryPeriod.UNKNOWN
    if any(term in normalized for term in ("annuel", "annuelle", "par an", "year")):
        period = SalaryPeriod.YEARLY
    elif any(term in normalized for term in ("mensuel", "mensuelle", "par mois", "month")):
        period = SalaryPeriod.MONTHLY
    elif any(term in normalized for term in ("horaire", "par heure", "hour")):
        period = SalaryPeriod.HOURLY

    currency = "EUR" if any(term in normalized for term in ("euro", "eur", "€")) else None
    minimum = numbers[0]
    maximum = numbers[1] if len(numbers) > 1 else numbers[0]
    return Salary(minimum, maximum, currency, period)


def _parse_number(value: str) -> float | None:
    compact = value.replace(" ", "")
    if compact.count(",") == 1 and len(compact.rsplit(",", 1)[1]) <= 2:
        compact = compact.replace(".", "").replace(",", ".")
    elif compact.count(".") == 1 and len(compact.rsplit(".", 1)[1]) <= 2:
        compact = compact.replace(",", "")
    else:
        compact = compact.replace(",", "").replace(".", "")
    try:
        return float(compact)
    except ValueError:
        return None
