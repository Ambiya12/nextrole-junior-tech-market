"""Credential-free portfolio demo support."""

from nextrole.demo.analytics import (
    FilterOptions,
    MarketKpis,
    NextSkillRecommendation,
    RoleMatch,
    filter_jobs,
    market_kpis,
    match_roles,
    recommend_next_skill,
    skill_demand,
)
from nextrole.demo.data import DemoDataError, DemoDataset, DemoJob, load_demo_dataset
from nextrole.demo.sample_data import SampleDatasetSummary, generate_sample_dataset

__all__ = [
    "DemoDataError",
    "DemoDataset",
    "DemoJob",
    "FilterOptions",
    "MarketKpis",
    "NextSkillRecommendation",
    "RoleMatch",
    "SampleDatasetSummary",
    "filter_jobs",
    "generate_sample_dataset",
    "load_demo_dataset",
    "market_kpis",
    "match_roles",
    "recommend_next_skill",
    "skill_demand",
]
