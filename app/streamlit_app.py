from __future__ import annotations

from html import escape
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from nextrole.demo import (
    DemoDataset,
    JobMatch,
    load_demo_dataset,
    match_jobs,
    match_roles,
    recommend_next_skill,
    skill_demand,
)

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "sample"
MATCH_THRESHOLD = 0.60

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
def load_data() -> DemoDataset:
    return load_demo_dataset(DATA_DIR)


def label(value: str) -> str:
    return ROLE_LABELS.get(value, value.replace("_", " ").replace("-", " ").title())


def job_cards(matches: tuple[JobMatch, ...]) -> str:
    cards = []
    for match in matches:
        skill_tags = "".join(
            f'<span class="skill-tag known">✓ {escape(skill)}</span>'
            for skill in match.matched_skills
        )
        skill_tags += "".join(
            f'<span class="skill-tag missing">{escape(skill)}</span>'
            for skill in match.missing_skills
        )
        cards.append(
            '<div class="job-card">'
            '<div class="job-card-header"><div>'
            f"<h3>{escape(match.title)}</h3>"
            f"<p>{escape(match.company)} · {escape(match.city)}</p>"
            "</div>"
            f'<span class="match-badge">{match.coverage_percentage:.0f}% fit</span>'
            "</div>"
            f'<div class="job-meta">{escape(label(match.contract_type))} · '
            f"Posted {escape(match.date_posted)}</div>"
            '<div class="skill-caption">Skills in this offer</div>'
            f'<div class="skill-tags">{skill_tags}</div>'
            "</div>"
        )
    return f'<div class="job-grid">{"".join(cards)}</div>'


st.set_page_config(
    page_title="NextRole — Find your next skill",
    page_icon="↗",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    :root {
        --ink: #172033;
        --muted: #647084;
        --blue: #3157D5;
        --blue-soft: #EEF2FF;
        --green: #137A68;
        --canvas: #F7F8FA;
        --surface: #FFFFFF;
        --line: #E3E7ED;
    }
    .stApp {
        background: var(--canvas);
        color: var(--ink);
    }
    .block-container {
        max-width: 1040px;
        padding: 2.1rem 2rem 4rem;
    }
    [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] {
        display: none;
    }
    h1, h2, h3, p {
        letter-spacing: -0.015em;
    }
    h1 {
        color: var(--ink);
        font-size: clamp(2.35rem, 5vw, 3.75rem) !important;
        line-height: 1.04 !important;
        letter-spacing: -0.045em !important;
        max-width: 760px;
        margin: 1.2rem 0 .75rem !important;
    }
    .brand {
        display: inline-flex;
        align-items: center;
        gap: .65rem;
        color: var(--ink);
        font-size: .95rem;
        font-weight: 750;
    }
    .brand-mark {
        display: inline-grid;
        place-items: center;
        width: 30px;
        height: 30px;
        border-radius: 9px;
        background: var(--blue);
        color: white;
        font-weight: 850;
    }
    .intro {
        color: var(--muted);
        font-size: 1.05rem;
        line-height: 1.65;
        max-width: 720px;
        margin-bottom: 1.2rem;
    }
    .data-notice {
        display: flex;
        align-items: flex-start;
        gap: .65rem;
        padding: .75rem .9rem;
        margin: .4rem 0 1.8rem;
        border: 1px solid #E8D9AE;
        border-radius: 11px;
        background: #FFFDF6;
        color: #66552D;
        font-size: .8rem;
        line-height: 1.45;
    }
    .data-notice strong {
        flex: 0 0 auto;
        color: #806615;
        font-size: .68rem;
        letter-spacing: .08em;
        text-transform: uppercase;
    }
    .step-label {
        color: var(--blue);
        font-size: .7rem;
        font-weight: 800;
        letter-spacing: .09em;
        text-transform: uppercase;
        margin-bottom: .25rem;
    }
    .step-title {
        color: var(--ink);
        font-size: 1.06rem;
        font-weight: 700;
        margin-bottom: .6rem;
    }
    [data-testid="stSelectbox"], [data-testid="stMultiSelect"] {
        margin-bottom: .45rem;
    }
    [data-baseweb="select"] > div {
        min-height: 48px;
        background: white !important;
        border-color: #CCD3DE;
        border-radius: 10px;
    }
    .results-heading {
        border-top: 1px solid var(--line);
        margin-top: 1.7rem;
        padding-top: 2rem;
    }
    .results-heading h2 {
        color: var(--ink);
        font-size: 1.65rem;
        margin: 0 0 .3rem;
    }
    .results-heading p {
        color: var(--muted);
        margin: 0 0 1rem;
    }
    [data-testid="stMetric"] {
        min-height: 118px;
        padding: 1rem 1.05rem;
        border: 1px solid var(--line);
        border-radius: 14px;
        background: var(--surface);
        box-shadow: 0 5px 18px rgba(23, 32, 51, .035);
    }
    [data-testid="stMetricLabel"] {
        color: var(--muted);
        font-size: .8rem;
    }
    [data-testid="stMetricValue"] {
        color: var(--ink);
        font-size: 1.7rem;
        font-weight: 750;
    }
    [data-testid="stMetricDelta"] {
        color: var(--muted);
        font-size: .72rem;
    }
    [data-testid="stMetricDelta"] svg {
        display: none;
    }
    .recommendation {
        position: relative;
        overflow: hidden;
        margin: 1rem 0 1.8rem;
        padding: 1.35rem 1.5rem;
        border: 1px solid #CED8FF;
        border-radius: 16px;
        background: var(--blue-soft);
    }
    .recommendation::after {
        content: "↗";
        position: absolute;
        right: 1rem;
        top: -.8rem;
        color: rgba(49, 87, 213, .08);
        font-size: 7rem;
        font-weight: 800;
    }
    .recommendation-label {
        position: relative;
        z-index: 1;
        color: var(--blue);
        font-size: .7rem;
        font-weight: 800;
        letter-spacing: .09em;
        text-transform: uppercase;
    }
    .recommendation h3 {
        position: relative;
        z-index: 1;
        color: var(--ink);
        font-size: 1.65rem;
        margin: .25rem 0 .35rem;
    }
    .recommendation p {
        position: relative;
        z-index: 1;
        color: #4D5C75;
        line-height: 1.55;
        margin: 0;
        max-width: 760px;
    }
    .chart-copy h2 {
        color: var(--ink);
        font-size: 1.35rem;
        margin: 0 0 .25rem;
    }
    .chart-copy p {
        color: var(--muted);
        font-size: .85rem;
        margin: 0 0 .65rem;
    }
    .jobs-heading {
        margin: 2rem 0 .8rem;
    }
    .jobs-heading h2 {
        color: var(--ink);
        font-size: 1.35rem;
        margin: 0 0 .3rem;
    }
    .jobs-heading p {
        color: var(--muted);
        font-size: .85rem;
        line-height: 1.55;
        margin: 0;
    }
    .skill-legend {
        display: flex;
        flex-wrap: wrap;
        gap: .65rem;
        margin: .75rem 0 1rem;
        color: var(--muted);
        font-size: .76rem;
    }
    .skill-legend span {
        display: inline-flex;
        align-items: center;
        gap: .35rem;
    }
    .legend-dot {
        width: 9px;
        height: 9px;
        border-radius: 999px;
    }
    .legend-dot.known {background: var(--green);}
    .legend-dot.missing {background: var(--blue);}
    .job-grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: .85rem;
        margin-bottom: 2.2rem;
    }
    .job-card {
        padding: 1.05rem 1.1rem;
        border: 1px solid var(--line);
        border-radius: 14px;
        background: white;
        box-shadow: 0 4px 16px rgba(23, 32, 51, .03);
    }
    .job-card-header {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: .75rem;
    }
    .job-card h3 {
        color: var(--ink);
        font-size: .98rem;
        line-height: 1.3;
        margin: 0 0 .22rem;
    }
    .job-card-header p {
        color: var(--muted);
        font-size: .77rem;
        margin: 0;
    }
    .match-badge {
        flex: 0 0 auto;
        padding: .3rem .48rem;
        border-radius: 7px;
        background: var(--blue-soft);
        color: var(--blue);
        font-size: .72rem;
        font-weight: 800;
    }
    .job-meta {
        color: #7B8494;
        font-size: .7rem;
        margin-top: .55rem;
    }
    .skill-caption {
        color: var(--muted);
        font-size: .68rem;
        font-weight: 700;
        margin: .75rem 0 .4rem;
    }
    .skill-tags {
        display: flex;
        flex-wrap: wrap;
        gap: .35rem;
    }
    .skill-tag {
        display: inline-flex;
        padding: .25rem .42rem;
        border-radius: 6px;
        font-size: .68rem;
        line-height: 1.2;
    }
    .skill-tag.known {
        background: #E6F5F1;
        color: #0D6657;
    }
    .skill-tag.missing {
        background: var(--blue-soft);
        color: #334FA5;
    }
    [data-testid="stPlotlyChart"] {
        padding: .45rem;
        border: 1px solid var(--line);
        border-radius: 14px;
        background: white;
    }
    .method-note {
        color: var(--muted);
        font-size: .78rem;
        line-height: 1.55;
        margin-top: 1.1rem;
    }
    [data-testid="stAlert"] {
        border-radius: 12px;
    }
    @media (max-width: 760px) {
        .block-container {
            padding: 4rem 1rem 3rem;
        }
        h1 {
            font-size: 2.35rem !important;
        }
        .data-notice {
            display: block;
        }
        .data-notice strong {
            display: block;
            margin-bottom: .25rem;
        }
        [data-testid="stHorizontalBlock"] {
            flex-wrap: wrap;
        }
        [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
            min-width: 100% !important;
            width: 100% !important;
            flex: 1 1 100% !important;
        }
        [data-testid="stMetric"] {
            min-height: 100px;
        }
        .job-grid {
            grid-template-columns: 1fr;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

dataset = load_data()
all_roles = sorted({job.role for job in dataset.jobs}, key=label)
skill_options = sorted(dataset.skill_names, key=lambda slug: dataset.skill_names[slug])

st.markdown(
    '<div class="brand"><span class="brand-mark">N</span><span>NextRole</span></div>',
    unsafe_allow_html=True,
)
st.title("Find the next skill to learn")
st.markdown(
    """
    <p class="intro">Choose the junior role you want and the skills you already know.
    NextRole will show where you stand and the single skill that could expand your options most.</p>
    <div class="data-notice"><strong>Demo data</strong><span>This experience uses a
    deterministic synthetic dataset. The figures demonstrate the product and are not findings
    about the French job market.</span></div>
    """,
    unsafe_allow_html=True,
)

role_column, skills_column = st.columns(2, gap="large")
with role_column:
    st.markdown(
        '<div class="step-label">Step 1</div><div class="step-title">Choose your target role</div>',
        unsafe_allow_html=True,
    )
    selected_role = st.selectbox(
        "Target role",
        all_roles,
        index=None,
        placeholder="Choose a role",
        format_func=label,
        label_visibility="collapsed",
    )

with skills_column:
    st.markdown(
        '<div class="step-label">Step 2</div><div class="step-title">Add skills you know</div>',
        unsafe_allow_html=True,
    )
    selected_skills = frozenset(
        st.multiselect(
            "Skills you already know",
            skill_options,
            default=[],
            placeholder="Select any skills",
            format_func=lambda slug: dataset.skill_names[slug],
            label_visibility="collapsed",
        )
    )

if selected_role is None:
    st.info("Choose a target role to see your skill recommendation.", icon="↗")
    st.stop()

role_jobs = tuple(job for job in dataset.jobs if job.role == selected_role)
role_match = match_roles(role_jobs, selected_skills, threshold=MATCH_THRESHOLD)[0]
offer_matches = match_jobs(dataset, role_jobs, selected_skills)
recommendation = recommend_next_skill(
    dataset,
    role_jobs,
    selected_skills,
    threshold=MATCH_THRESHOLD,
)

st.markdown(
    f"""
    <div class="results-heading">
        <h2>Your {label(selected_role)} skill snapshot</h2>
        <p>Based on the requested skills in the selected sample postings.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

metric_columns = st.columns(3, gap="medium")
metric_columns[0].metric(
    "Postings analyzed",
    len(role_jobs),
    label(selected_role),
    delta_color="off",
)
metric_columns[1].metric(
    "Average skills matched",
    f"{role_match.average_coverage:.0f}%",
    "across these postings",
    delta_color="off",
)
metric_columns[2].metric(
    "Matching job offers",
    f"{100 * role_match.accessible_jobs / role_match.total_jobs:.0f}%",
    (
        f"{role_match.accessible_jobs} of {role_match.total_jobs} "
        f"at {MATCH_THRESHOLD:.0%}+ skill fit"
    ),
    delta_color="off",
)

if recommendation is None:
    st.success(
        "You selected every skill represented in these postings. There is no additional "
        "skill to recommend from this sample.",
        icon="✅",
    )
else:
    if recommendation.newly_accessible_jobs:
        impact_copy = (
            f"It moves <strong>{recommendation.newly_accessible_jobs}</strong> more "
            f"posting{'' if recommendation.newly_accessible_jobs == 1 else 's'} to or above "
            f"the {MATCH_THRESHOLD:.0%} benchmark."
        )
    else:
        impact_copy = (
            f"No single skill immediately moves another posting above the "
            f"{MATCH_THRESHOLD:.0%} benchmark, but this is the strongest next step."
        )
    st.markdown(
        f"""
        <div class="recommendation">
            <div class="recommendation-label">Recommended next skill</div>
            <h3>{recommendation.skill_name}</h3>
            <p>{impact_copy} It appears in <strong>{recommendation.affected_jobs}</strong>
            selected-role postings and adds an average of
            <strong>{recommendation.average_coverage_gain:.1f} percentage points</strong>
            wherever it is requested.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown(
    f"""
    <div class="jobs-heading">
        <h2>Dummy job offers ranked by your skills</h2>
        <p>All {len(offer_matches)} {label(selected_role)} offers are ordered by skill fit.
        Each percentage is the share of that offer's requested skills you selected.</p>
    </div>
    <div class="skill-legend">
        <span><i class="legend-dot known"></i>Skill you know</span>
        <span><i class="legend-dot missing"></i>Skill to learn</span>
    </div>
    {job_cards(offer_matches)}
    """,
    unsafe_allow_html=True,
)

demand = skill_demand(dataset, role_jobs)
demand_frame = pd.DataFrame(
    [
        {
            "Skill": item.skill_name,
            "Posting share": item.posting_percentage,
            "Postings": item.posting_count,
            "Status": "Already know" if item.skill_slug in selected_skills else "Opportunity",
        }
        for item in reversed(demand)
    ]
)

st.markdown(
    f"""
    <div class="chart-copy">
        <h2>Skills requested for {label(selected_role)}</h2>
        <p>Every skill found in this role's sample postings. Green marks skills you selected.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

skill_figure = px.bar(
    demand_frame,
    x="Posting share",
    y="Skill",
    orientation="h",
    color="Status",
    color_discrete_map={"Already know": "#137A68", "Opportunity": "#3157D5"},
    text="Posting share",
    custom_data=["Postings", "Status"],
)
skill_figure.update_traces(
    texttemplate="%{text:.0f}%",
    textposition="outside",
    cliponaxis=False,
    hovertemplate=(
        "<b>%{y}</b><br>%{customdata[0]} postings · %{x:.1f}%<br>%{customdata[1]}<extra></extra>"
    ),
)
skill_figure.update_layout(
    height=max(430, 70 + 42 * len(demand_frame)),
    margin={"l": 12, "r": 30, "t": 48, "b": 20},
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font={"family": "Inter, ui-sans-serif, system-ui", "color": "#172033"},
    legend={"title": None, "orientation": "h", "y": 1.12, "x": 0},
    xaxis_title="Share of postings",
    yaxis_title=None,
    xaxis_range=[0, max(105, float(demand_frame["Posting share"].max()) + 12)],
)
skill_figure.update_xaxes(ticksuffix="%", gridcolor="#E9ECF1", zeroline=False)
skill_figure.update_yaxes(gridcolor="rgba(0,0,0,0)", zeroline=False)
st.plotly_chart(
    skill_figure,
    width="stretch",
    config={"displayModeBar": False, "responsive": True},
)

st.markdown(
    f"""
    <p class="method-note"><strong>How the comparison works:</strong> each posting's coverage is
    the share of its requested skills that you selected. The {MATCH_THRESHOLD:.0%} benchmark is a
    simple reference point—not a hiring probability or an assessment of proficiency.</p>
    """,
    unsafe_allow_html=True,
)
