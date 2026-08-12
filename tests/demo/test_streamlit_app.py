from pathlib import Path

from streamlit.testing.v1 import AppTest

from nextrole.demo import load_demo_dataset

ROOT = Path(__file__).parents[2]
APP_PATH = ROOT / "app" / "streamlit_app.py"
DATA_DIR = ROOT / "data" / "sample"


def load_app() -> AppTest:
    return AppTest.from_file(str(APP_PATH)).run(timeout=30)


def test_streamlit_demo_starts_with_a_clear_guided_prompt() -> None:
    app = load_app()

    assert not app.exception
    assert app.title[0].value == "Find the next skill to learn"
    assert not app.tabs
    assert not app.metric
    assert app.selectbox[0].label == "Target role"
    assert app.selectbox[0].value is None
    assert app.multiselect[0].label == "Skills you already know"
    assert app.multiselect[0].value == []
    assert "Choose a target role" in app.info[0].value
    assert any("Demo data" in item.value for item in app.markdown)


def test_selecting_a_role_shows_the_skill_snapshot_and_recommendation() -> None:
    app = load_app()

    app.selectbox[0].set_value("data_analyst").run(timeout=30)

    assert not app.exception
    assert [metric.label for metric in app.metric] == [
        "Postings analyzed",
        "Average skills matched",
        "Matching job offers",
    ]
    assert app.metric[0].value == "12"
    assert app.metric[1].value == "0%"
    assert app.metric[2].value == "0%"
    assert len(app.get("plotly_chart")) == 1
    assert any("Your Data Analyst skill snapshot" in item.value for item in app.markdown)
    assert any("Recommended next skill" in item.value for item in app.markdown)
    assert any("Dummy job offers ranked by your skills" in item.value for item in app.markdown)
    assert sum(item.value.count('class="job-card"') for item in app.markdown) == 12


def test_known_skills_update_coverage_and_complete_selection_has_no_recommendation() -> None:
    app = load_app()
    app.selectbox[0].set_value("data_analyst")
    app.multiselect[0].set_value(["python", "sql", "excel"])
    app.run(timeout=30)

    assert not app.exception
    assert app.metric[1].value != "0%"
    assert any("Recommended next skill" in item.value for item in app.markdown)

    all_skills = sorted(load_demo_dataset(DATA_DIR).skill_names)
    app.multiselect[0].set_value(all_skills).run(timeout=30)

    assert not app.exception
    assert "selected every skill" in app.success[0].value
    assert app.metric[2].value == "100%"
    assert not any("Recommended next skill" in item.value for item in app.markdown)
