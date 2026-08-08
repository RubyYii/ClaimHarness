from pathlib import Path
from types import SimpleNamespace
from contextlib import nullcontext

import pytest
import apps.problem_bridge_wizard as ui


def test_output_renderer_dispatches_legacy_packages_by_actual_artifact_type(
    tmp_path,
    monkeypatch,
):
    rendered: list[tuple[str, Path]] = []
    monkeypatch.setattr(
        ui, "_render_document_intake_output", lambda path: rendered.append(("intake", path))
    )
    monkeypatch.setattr(
        ui, "_render_question_discovery_output", lambda path: rendered.append(("discovery", path))
    )
    monkeypatch.setattr(
        ui, "_render_claim_audit_output", lambda path: rendered.append(("audit", path))
    )
    monkeypatch.setattr(
        ui, "_render_friendly_output", lambda path: rendered.append(("alignment", path))
    )

    fixtures = [
        ("intake", "extracted_text.md"),
        ("discovery", "question_brief.md"),
        ("audit", "claim_table.csv"),
        ("alignment", "problem_card.md"),
    ]
    for expected, sentinel in fixtures:
        out = tmp_path / expected
        out.mkdir()
        (out / sentinel).write_text("fixture\n", encoding="utf-8")
        ui._render_output_for_run(out)

    assert [kind for kind, _path in rendered] == [
        "intake",
        "discovery",
        "audit",
        "alignment",
    ]


def test_output_renderer_rejects_mixed_legacy_packages(tmp_path):
    out = tmp_path / "mixed"
    out.mkdir()
    (out / "claim_table.csv").write_text("claim_id,status\nC001,supported\n", encoding="utf-8")
    (out / "extracted_text.md").write_text("legacy intake\n", encoding="utf-8")

    with pytest.raises(ValueError, match="exactly one recognizable package type"):
        ui._output_kind(out)


def test_legacy_claim_audit_marks_missing_diagnostics_unavailable(tmp_path, monkeypatch):
    out = tmp_path / "legacy-audit"
    out.mkdir()
    (out / "claim_table.csv").write_text(
        "claim_id,status,risk_level,text,suggested_revision\n"
        "C001,supported,low,Supported claim,\n"
        "C002,needs_human_review,high,Review claim,Check manually\n",
        encoding="utf-8",
    )
    metrics = {}
    messages = []

    class MetricColumn:
        def metric(self, label, value):
            metrics[label] = value

    monkeypatch.setattr(ui.st, "subheader", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(ui.st, "columns", lambda count: [MetricColumn() for _ in range(count)])
    monkeypatch.setattr(ui.st, "caption", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(ui.st, "info", messages.append)
    monkeypatch.setattr(ui.st, "warning", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(ui.st, "markdown", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(ui.st, "dataframe", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(ui.st, "success", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(ui.st, "code", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(ui.st, "expander", lambda *_args, **_kwargs: nullcontext())
    monkeypatch.setattr(ui, "_render_share_controls", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(ui, "_render_report_export_buttons", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(ui, "_text", lambda en, _zh: en)

    ui._render_claim_audit_output(out)

    assert metrics == {
        "Claims": 2,
        "Support relations": "Unavailable",
        "Needs human review": "1/2",
        "Pending review items": "Unavailable",
    }
    assert messages and "not treated as zero" in messages[0]


def test_invalid_optional_audit_json_is_nonfatal(tmp_path, monkeypatch):
    path = tmp_path / "audit_diagnostics.json"
    path.write_text("{not-json", encoding="utf-8")
    warnings = []
    monkeypatch.setattr(ui.st, "warning", warnings.append)
    monkeypatch.setattr(ui, "_text", lambda en, _zh: en)

    assert ui._read_optional_json_object(path, "audit diagnostics") is None
    assert warnings and "Could not read audit diagnostics" in warnings[0]


def test_project_output_path_rejects_another_projects_run(tmp_path, monkeypatch):
    out = tmp_path / "run-a"
    out.mkdir()
    monkeypatch.setattr(ui, "_resolve_ui_run_for_read", lambda path: Path(path))
    monkeypatch.setattr(ui, "load_run_identity", lambda _path: {"project_id": "project-a"})
    monkeypatch.setattr(ui, "is_run_complete", lambda _path: True)

    assert ui._validated_project_output_path(out, "project-b") is None
    assert ui._validated_project_output_path(out, "project-a") == out


def test_previous_result_stays_collapsed_until_user_requests_it(tmp_path, monkeypatch):
    out = tmp_path / "previous"
    out.mkdir()
    messages = []
    rendered = []
    monkeypatch.setattr(ui.st, "info", messages.append)
    monkeypatch.setattr(ui.st, "checkbox", lambda *args, **kwargs: False)

    ui._render_previous_result_card(
        out,
        rendered.append,
        key_suffix="fixture",
        label="workflow result",
    )

    assert messages and "does not include edits" in messages[0]
    assert rendered == []

    monkeypatch.setattr(ui.st, "checkbox", lambda *args, **kwargs: True)
    ui._render_previous_result_card(
        out,
        rendered.append,
        key_suffix="fixture",
        label="workflow result",
    )
    assert rendered == [out]


def test_completed_archive_payload_is_cached_across_rerenders(tmp_path, monkeypatch):
    calls = []
    ui._cached_archive_payload.clear()
    monkeypatch.setattr(
        ui,
        "_make_archive",
        lambda path, include_source_files=False: calls.append(
            (Path(path), include_source_files)
        )
        or b"archive",
    )
    token = f"completion-{tmp_path.name}"

    first = ui._cached_archive_payload(str(tmp_path), token, False)
    second = ui._cached_archive_payload(str(tmp_path), token, False)

    assert first == second == b"archive"
    assert calls == [(tmp_path, False)]


def test_completed_report_payload_is_cached_across_rerenders(tmp_path, monkeypatch):
    calls = []
    docx = tmp_path / "export_report.docx"
    pdf = tmp_path / "export_report.pdf"
    docx.write_bytes(b"docx")
    pdf.write_bytes(b"pdf")
    ui._cached_report_payload.clear()

    def fake_export(path):
        calls.append(Path(path))
        return SimpleNamespace(docx_path=docx, pdf_path=pdf)

    monkeypatch.setattr(ui, "export_output_report", fake_export)
    token = f"completion-{tmp_path.name}"

    first = ui._cached_report_payload(str(tmp_path), token)
    second = ui._cached_report_payload(str(tmp_path), token)

    assert first == second == ("export_report.docx", b"docx", "export_report.pdf", b"pdf")
    assert calls == [tmp_path]


def test_completed_run_cache_token_changes_with_governance_snapshot(tmp_path, monkeypatch):
    (tmp_path / ui.RUN_IDENTITY_NAME).write_text("{}\n", encoding="utf-8")
    (tmp_path / "run_complete.json").write_text('{"complete": true}\n', encoding="utf-8")
    monkeypatch.setattr(ui, "is_run_complete", lambda _path: True)

    immutable_only = ui._completed_run_cache_token(tmp_path)
    (tmp_path / "project_record.json").write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(
        ui,
        "snapshot_project_governance",
        lambda _path: {"project_record.json": b"revision-one"},
    )
    revision_one = ui._completed_run_cache_token(tmp_path)
    monkeypatch.setattr(
        ui,
        "snapshot_project_governance",
        lambda _path: {"project_record.json": b"revision-two"},
    )
    revision_two = ui._completed_run_cache_token(tmp_path)

    assert immutable_only != revision_one
    assert revision_one != revision_two


def test_source_inclusive_share_archive_bypasses_cache(tmp_path, monkeypatch):
    out = tmp_path / "run"
    (out / "source_files").mkdir(parents=True)
    cached_calls = []
    direct_calls = []
    downloads = []
    monkeypatch.setattr(ui, "_text", lambda en, _zh: en)
    monkeypatch.setattr(ui, "_completed_run_cache_token", lambda _path: "token")
    monkeypatch.setattr(
        ui,
        "_cached_archive_payload",
        lambda *args: cached_calls.append(args) or b"cached",
    )
    monkeypatch.setattr(
        ui,
        "_make_archive",
        lambda path, include_source_files=False: direct_calls.append(
            (path, include_source_files)
        )
        or b"direct",
    )
    monkeypatch.setattr(ui.st, "caption", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(ui.st, "warning", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        ui.st,
        "checkbox",
        lambda _label, **kwargs: str(kwargs.get("key", "")).startswith("include_source_files_"),
    )
    monkeypatch.setattr(
        ui.st,
        "download_button",
        lambda _label, data, **_kwargs: downloads.append(data),
    )
    monkeypatch.setattr(ui.st, "expander", lambda *_args, **_kwargs: nullcontext())
    monkeypatch.setattr(ui.st, "button", lambda *_args, **_kwargs: False)

    ui._render_share_controls(out, "fixture", allow_source_files=True)

    assert cached_calls == []
    assert direct_calls == [(out, True)]
    assert downloads == [b"direct"]


def test_sidebar_radio_keeps_keyboard_input_focusable():
    source = Path("apps/problem_bridge_wizard.py").read_text(encoding="utf-8")
    selector = 'label[data-baseweb="radio"] > div:first-child'
    block = source.split(selector, 1)[1].split("}", 1)[0]

    assert "display: none" not in block
    assert "clip: rect(0, 0, 0, 0)" in block
    assert 'label[data-baseweb="radio"]:has(input:focus-visible)' in source
