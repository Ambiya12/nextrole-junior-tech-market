"""Pure analytical calculations shared by the demo interface and tests."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass

from nextrole.demo.data import DemoDataset, DemoJob


@dataclass(frozen=True)
class FilterOptions:
    roles: frozenset[str] = frozenset()
    cities: frozenset[str] = frozenset()
    contracts: frozenset[str] = frozenset()
    work_modes: frozenset[str] = frozenset()


@dataclass(frozen=True)
class CategoryCount:
    key: str
    count: int


@dataclass(frozen=True)
class MarketKpis:
    total_postings: int
    unique_companies: int
    unique_cities: int
    flexible_work_percentage: float
    most_requested_role: str | None
    most_requested_skill: str | None


@dataclass(frozen=True)
class SkillDemand:
    skill_slug: str
    skill_name: str
    category: str
    posting_count: int
    posting_percentage: float
    role_count: int


@dataclass(frozen=True)
class SkillPair:
    first_skill: str
    second_skill: str
    posting_count: int


@dataclass(frozen=True)
class RoleMatch:
    role: str
    average_coverage: float
    accessible_jobs: int
    total_jobs: int


@dataclass(frozen=True)
class NextSkillRecommendation:
    skill_slug: str
    skill_name: str
    newly_accessible_jobs: int
    affected_jobs: int
    average_coverage_gain: float


def filter_jobs(jobs: tuple[DemoJob, ...], filters: FilterOptions) -> tuple[DemoJob, ...]:
    return tuple(
        job
        for job in jobs
        if (not filters.roles or job.role in filters.roles)
        and (not filters.cities or job.city in filters.cities)
        and (not filters.contracts or job.contract_type in filters.contracts)
        and (not filters.work_modes or job.work_mode in filters.work_modes)
    )


def count_by(jobs: tuple[DemoJob, ...], attribute: str) -> tuple[CategoryCount, ...]:
    counts = Counter(str(getattr(job, attribute)) for job in jobs)
    return tuple(
        CategoryCount(key, count)
        for key, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    )


def market_kpis(dataset: DemoDataset, jobs: tuple[DemoJob, ...]) -> MarketKpis:
    role_counts = count_by(jobs, "role")
    demand = skill_demand(dataset, jobs)
    flexible_count = sum(job.work_mode in {"remote", "hybrid"} for job in jobs)
    return MarketKpis(
        total_postings=len(jobs),
        unique_companies=len({job.company for job in jobs}),
        unique_cities=len({job.city for job in jobs}),
        flexible_work_percentage=round(100 * flexible_count / len(jobs), 1) if jobs else 0.0,
        most_requested_role=role_counts[0].key if role_counts else None,
        most_requested_skill=demand[0].skill_name if demand else None,
    )


def skill_demand(dataset: DemoDataset, jobs: tuple[DemoJob, ...]) -> tuple[SkillDemand, ...]:
    job_counts: Counter[str] = Counter()
    roles: dict[str, set[str]] = defaultdict(set)
    for job in jobs:
        for slug in job.skill_slugs:
            job_counts[slug] += 1
            roles[slug].add(job.role)

    return tuple(
        SkillDemand(
            skill_slug=slug,
            skill_name=dataset.skill_names[slug],
            category=dataset.skill_categories[slug],
            posting_count=count,
            posting_percentage=round(100 * count / len(jobs), 1) if jobs else 0.0,
            role_count=len(roles[slug]),
        )
        for slug, count in sorted(
            job_counts.items(),
            key=lambda item: (-item[1], dataset.skill_names[item[0]]),
        )
    )


def skill_pairs(dataset: DemoDataset, jobs: tuple[DemoJob, ...]) -> tuple[SkillPair, ...]:
    counts: Counter[tuple[str, str]] = Counter()
    for job in jobs:
        ordered = sorted(job.skill_slugs)
        for first_index, first_slug in enumerate(ordered):
            for second_slug in ordered[first_index + 1 :]:
                counts[(first_slug, second_slug)] += 1
    return tuple(
        SkillPair(dataset.skill_names[first], dataset.skill_names[second], count)
        for (first, second), count in sorted(
            counts.items(),
            key=lambda item: (-item[1], item[0]),
        )
    )


def match_roles(
    jobs: tuple[DemoJob, ...],
    candidate_skills: frozenset[str],
    *,
    threshold: float = 0.6,
) -> tuple[RoleMatch, ...]:
    _validate_threshold(threshold)
    coverage_by_role: dict[str, list[float]] = defaultdict(list)
    for job in jobs:
        coverage = len(candidate_skills & job.skill_slugs) / len(job.skill_slugs)
        coverage_by_role[job.role].append(coverage)

    return tuple(
        RoleMatch(
            role=role,
            average_coverage=round(100 * sum(coverages) / len(coverages), 1),
            accessible_jobs=sum(coverage >= threshold for coverage in coverages),
            total_jobs=len(coverages),
        )
        for role, coverages in sorted(
            coverage_by_role.items(),
            key=lambda item: (-sum(item[1]) / len(item[1]), item[0]),
        )
    )


def recommend_next_skill(
    dataset: DemoDataset,
    jobs: tuple[DemoJob, ...],
    candidate_skills: frozenset[str],
    *,
    threshold: float = 0.6,
) -> NextSkillRecommendation | None:
    _validate_threshold(threshold)
    candidates = set(dataset.skill_names) - set(candidate_skills)
    recommendations: list[NextSkillRecommendation] = []

    for skill_slug in candidates:
        affected_jobs = 0
        newly_accessible_jobs = 0
        coverage_gain = 0.0
        for job in jobs:
            if skill_slug not in job.skill_slugs:
                continue
            affected_jobs += 1
            current_coverage = len(candidate_skills & job.skill_slugs) / len(job.skill_slugs)
            improved_coverage = (len(candidate_skills & job.skill_slugs) + 1) / len(job.skill_slugs)
            coverage_gain += improved_coverage - current_coverage
            if current_coverage < threshold <= improved_coverage:
                newly_accessible_jobs += 1
        if affected_jobs:
            recommendations.append(
                NextSkillRecommendation(
                    skill_slug=skill_slug,
                    skill_name=dataset.skill_names[skill_slug],
                    newly_accessible_jobs=newly_accessible_jobs,
                    affected_jobs=affected_jobs,
                    average_coverage_gain=round(100 * coverage_gain / affected_jobs, 1),
                )
            )

    return min(
        recommendations,
        key=lambda item: (
            -item.newly_accessible_jobs,
            -item.affected_jobs,
            -item.average_coverage_gain,
            item.skill_name,
        ),
        default=None,
    )


def _validate_threshold(threshold: float) -> None:
    if not 0 < threshold <= 1:
        raise ValueError("match threshold must be greater than 0 and at most 1")
