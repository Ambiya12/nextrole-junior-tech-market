from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_streamlit_demo_renders_without_exceptions() -> None:
    app_path = Path(__file__).parents[2] / "app" / "streamlit_app.py"

    app = AppTest.from_file(str(app_path)).run(timeout=30)

    assert not app.exception
    assert app.title[0].value == "NextRole"
    assert len(app.metric) == 5
