from pathlib import Path

import pytest

from nextrole.demo import (
    FilterOptions,
    filter_jobs,
    load_demo_dataset,
    market_kpis,
    match_roles,
    recommend_next_skill,
    skill_demand,
)
from nextrole.demo.analytics import count_by, skill_pairs

DATA_DIR = Path(__file__).parents[2] / "data" / "sample"


@pytest.fixture(scope="module")
def dataset():  # type: ignore[no-untyped-def]
    return load_demo_dataset(DATA_DIR)


def test_filters_and_kpis_reconcile_to_the_same_jobs(dataset) -> None:  # type: ignore[no-untyped-def]
    jobs = filter_jobs(
        dataset.jobs,
        FilterOptions(
            roles=frozenset({"data_analyst"}),
            cities=frozenset({"Paris"}),
        ),
    )
    kpis = market_kpis(dataset, jobs)

    assert jobs
    assert all(job.role == "data_analyst" and job.city == "Paris" for job in jobs)
    assert kpis.total_postings == len(jobs)
    assert kpis.unique_cities == 1


def test_skill_demand_and_pairs_are_ranked_deterministically(dataset) -> None:  # type: ignore[no-untyped-def]
    first_demand = skill_demand(dataset, dataset.jobs)
    second_demand = skill_demand(dataset, tuple(reversed(dataset.jobs)))
    pairs = skill_pairs(dataset, dataset.jobs)

    assert first_demand == second_demand
    assert first_demand[0].posting_count >= first_demand[-1].posting_count
    assert pairs[0].posting_count >= pairs[-1].posting_count
    assert count_by(dataset.jobs, "role")[0].count == 12


def test_matcher_scores_roles_and_recommends_an_unselected_skill(dataset) -> None:  # type: ignore[no-untyped-def]
    selected = frozenset({"python", "sql", "excel", "git"})

    matches = match_roles(dataset.jobs, selected, threshold=0.6)
    recommendation = recommend_next_skill(dataset, dataset.jobs, selected, threshold=0.6)

    assert len(matches) == 7
    assert matches[0].average_coverage >= matches[-1].average_coverage
    assert all(item.accessible_jobs <= item.total_jobs for item in matches)
    assert recommendation is not None
    assert recommendation.skill_slug not in selected
    assert recommendation.affected_jobs > 0


@pytest.mark.parametrize("threshold", [0.0, -0.1, 1.1])
def test_matcher_rejects_invalid_thresholds(dataset, threshold: float) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ValueError, match="match threshold"):
        match_roles(dataset.jobs, frozenset(), threshold=threshold)
