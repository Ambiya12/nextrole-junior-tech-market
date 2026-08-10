from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

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

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "sample"

ROLE_LABELS = {
    "data_analyst": "Data Analyst",
    "bi_analyst": "BI Analyst",
    "data_engineer": "Data Engineer",
    "data_scientist": "Data Scientist",
    "frontend_developer": "Frontend Developer",
    "backend_developer": "Backend Developer",
    "fullstack_developer": "Full-Stack Developer",
}


@st.cache_data
def load_data() -> object:
    return load_demo_dataset(DATA_DIR)


def label(value: str) -> str:
    return ROLE_LABELS.get(value, value.replace("_", " ").title())


st.set_page_config(
    page_title="NextRole — Junior Tech Market",
    page_icon="↗",
    layout="wide",
)

st.markdown(
    """
    <style>
    .block-container {padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1320px;}
    [data-testid="stMetric"] {background: white; border: 1px solid #dbe5e4;
        padding: 1rem; border-radius: 14px;}
    [data-testid="stMetricValue"] {color: #0f766e;}
    .demo-banner {background: #fff7ed; border: 1px solid #fdba74; color: #9a3412;
        padding: .8rem 1rem; border-radius: 12px; margin: .8rem 0 1.4rem;}
    .recommendation {background: linear-gradient(135deg, #0f766e, #115e59); color: white;
        padding: 1.25rem 1.4rem; border-radius: 16px; margin: .75rem 0 1.2rem;}
    .recommendation h3 {color: white; margin: 0 0 .35rem;}
    </style>
    """,
    unsafe_allow_html=True,
)

dataset = load_data()

st.title("NextRole")
st.caption("Junior technology job-market intelligence for France")
st.markdown(
    '<div class="demo-banner"><strong>Portfolio demo:</strong> This interface uses a '
    "deterministic synthetic dataset. Its figures demonstrate the product and analytical "
    "workflow; they are not claims about the real French job market.</div>",
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("Explore the market")
    all_roles = sorted({job.role for job in dataset.jobs}, key=label)
    selected_roles = st.multiselect("Roles", all_roles, format_func=label)
    all_cities = sorted({job.city for job in dataset.jobs})
    selected_cities = st.multiselect("Cities", all_cities)
    all_contracts = sorted({job.contract_type for job in dataset.jobs}, key=label)
    selected_contracts = st.multiselect("Contracts", all_contracts, format_func=label)
    all_work_modes = sorted({job.work_mode for job in dataset.jobs}, key=label)
    selected_work_modes = st.multiselect("Work modes", all_work_modes, format_func=label)
    st.divider()
    st.caption(f"{len(dataset.jobs)} synthetic postings · reproducible seed")

filters = FilterOptions(
    roles=frozenset(selected_roles),
    cities=frozenset(selected_cities),
    contracts=frozenset(selected_contracts),
    work_modes=frozenset(selected_work_modes),
)
jobs = filter_jobs(dataset.jobs, filters)
kpis = market_kpis(dataset, jobs)

if not jobs:
    st.warning("No postings match this filter combination. Remove one or more filters.")
    st.stop()

overview_tab, comparison_tab, skills_tab, matcher_tab, method_tab = st.tabs(
    ["Market overview", "Role comparison", "Skills intelligence", "Career matcher", "Method"]
)

with overview_tab:
    metric_columns = st.columns(5)
    metric_columns[0].metric("Postings", f"{kpis.total_postings:,}")
    metric_columns[1].metric("Companies", kpis.unique_companies)
    metric_columns[2].metric("Cities", kpis.unique_cities)
    metric_columns[3].metric("Flexible work", f"{kpis.flexible_work_percentage:.1f}%")
    metric_columns[4].metric("Top skill", kpis.most_requested_skill or "—")

    left, right = st.columns((1.25, 1))
    role_frame = pd.DataFrame(
        [{"Role": label(item.key), "Postings": item.count} for item in count_by(jobs, "role")]
    )
    left.plotly_chart(
        px.bar(
            role_frame,
            x="Postings",
            y="Role",
            orientation="h",
            color="Postings",
            color_continuous_scale=["#99f6e4", "#0f766e"],
            title="Postings by role",
        ).update_layout(coloraxis_showscale=False, yaxis_categoryorder="total ascending"),
        width="stretch",
    )
    contract_frame = pd.DataFrame(
        [
            {"Contract": label(item.key), "Postings": item.count}
            for item in count_by(jobs, "contract_type")
        ]
    )
    right.plotly_chart(
        px.pie(
            contract_frame,
            names="Contract",
            values="Postings",
            hole=0.55,
            title="Contract mix",
            color_discrete_sequence=px.colors.qualitative.Safe,
        ),
        width="stretch",
    )

    city_frame = pd.DataFrame(
        [{"City": item.key, "Postings": item.count} for item in count_by(jobs, "city")]
    )
    st.plotly_chart(
        px.bar(
            city_frame,
            x="City",
            y="Postings",
            color="Postings",
            color_continuous_scale=["#ccfbf1", "#115e59"],
            title="Geographic distribution",
        ).update_layout(coloraxis_showscale=False),
        width="stretch",
    )

with comparison_tab:
    st.subheader("Compare role requirements")
    comparison_roles = st.multiselect(
        "Choose two or three roles",
        all_roles,
        default=all_roles[:2],
        max_selections=3,
        format_func=label,
        key="comparison_roles",
    )
    comparison_rows: list[dict[str, object]] = []
    for role in comparison_roles:
        role_jobs = tuple(job for job in jobs if job.role == role)
        comparison_rows.extend(
            {
                "Role": label(role),
                "Skill": item.skill_name,
                "Posting %": item.posting_percentage,
            }
            for item in skill_demand(dataset, role_jobs)[:8]
        )
    if comparison_rows:
        comparison_frame = pd.DataFrame(comparison_rows)
        st.plotly_chart(
            px.bar(
                comparison_frame,
                x="Posting %",
                y="Skill",
                color="Role",
                barmode="group",
                orientation="h",
                title="Top skills within each selected role",
            ),
            width="stretch",
        )
    else:
        st.info("Select at least one role that remains in the active market filters.")

with skills_tab:
    demand = skill_demand(dataset, jobs)
    demand_frame = pd.DataFrame(
        [
            {
                "Skill": item.skill_name,
                "Category": label(item.category),
                "Postings": item.posting_count,
                "Posting %": item.posting_percentage,
                "Roles": item.role_count,
            }
            for item in demand[:15]
        ]
    )
    st.plotly_chart(
        px.bar(
            demand_frame,
            x="Postings",
            y="Skill",
            orientation="h",
            color="Roles",
            color_continuous_scale=["#a7f3d0", "#065f46"],
            title="Most requested technical skills",
        ).update_layout(yaxis_categoryorder="total ascending"),
        width="stretch",
    )
    first, second = st.columns((1.1, 1))
    first.subheader("Demand and transferability")
    first.dataframe(demand_frame, hide_index=True, width="stretch")
    pair_frame = pd.DataFrame([asdict(pair) for pair in skill_pairs(dataset, jobs)[:12]])
    pair_frame = pair_frame.rename(
        columns={
            "first_skill": "First skill",
            "second_skill": "Second skill",
            "posting_count": "Postings",
        }
    )
    second.subheader("Frequent skill pairs")
    second.dataframe(pair_frame, hide_index=True, width="stretch")

with matcher_tab:
    st.subheader("Match your skills to observed requirements")
    st.caption(
        "Coverage is the share of skills attached to each posting that you selected. "
        "It is not a probability of being hired."
    )
    skill_options = sorted(dataset.skill_names, key=lambda slug: dataset.skill_names[slug])
    selected_skills = frozenset(
        st.multiselect(
            "Skills you already know",
            skill_options,
            default=[slug for slug in ("python", "sql", "excel", "git") if slug in skill_options],
            format_func=lambda slug: dataset.skill_names[slug],
        )
    )
    threshold = (
        st.slider(
            "Accessible-job coverage threshold",
            min_value=40,
            max_value=100,
            value=60,
            step=5,
            format="%d%%",
        )
        / 100
    )
    recommendation = recommend_next_skill(dataset, jobs, selected_skills, threshold=threshold)
    if recommendation:
        st.markdown(
            f'<div class="recommendation"><h3>Recommended next skill: '
            f"{recommendation.skill_name}</h3>It crosses the {threshold:.0%} coverage threshold "
            f"for <strong>{recommendation.newly_accessible_jobs}</strong> additional postings "
            f"and appears in {recommendation.affected_jobs} filtered postings.</div>",
            unsafe_allow_html=True,
        )

    role_matches = match_roles(jobs, selected_skills, threshold=threshold)
    match_frame = pd.DataFrame(
        [
            {
                "Role": label(item.role),
                "Average coverage": item.average_coverage,
                "Accessible jobs": item.accessible_jobs,
                "Total jobs": item.total_jobs,
            }
            for item in role_matches
        ]
    )
    st.plotly_chart(
        px.bar(
            match_frame,
            x="Average coverage",
            y="Role",
            orientation="h",
            color="Accessible jobs",
            color_continuous_scale=["#d1fae5", "#047857"],
            range_x=[0, 100],
            title="Skill coverage by role",
        ).update_layout(yaxis_categoryorder="total ascending"),
        width="stretch",
    )
    st.dataframe(match_frame, hide_index=True, width="stretch")

with method_tab:
    st.subheader("How to read this demo")
    st.markdown(
        """
        - **Dataset:** 84 deterministic synthetic postings across seven role families.
        - **Purpose:** demonstrate the interface, filters, KPI logic, and recommendation workflow.
        - **Job coverage:** selected skills divided by the skills attached to one posting.
        - **Role coverage:** average job coverage within a role.
        - **Next skill:** ranked first by newly accessible postings, then by total affected
          postings.
        - **Important:** coverage is not employability and does not account for proficiency,
          education, experience, soft skills, or optional versus mandatory requirements.
        """
    )
    st.json(dataset.metadata)
