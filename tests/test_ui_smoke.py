import pytest


streamlit_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = streamlit_testing.AppTest


def test_streamlit_workbench_renders_project_and_document_intake_controls():
    app = AppTest.from_file("apps/problem_bridge_wizard.py").run(timeout=30)

    assert not app.exception
    assert len(app.sidebar.radio) == 1
    assert any(button.label == "Start a new project" for button in app.sidebar.button)

    app.sidebar.radio[0].set_value("Document intake").run(timeout=30)

    assert not app.exception
    assert any("OCR" in checkbox.label for checkbox in app.checkbox)
