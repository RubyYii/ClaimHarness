from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from problem_bridge import dyad
from problem_bridge.requirements import confirm_requirements, current_trace
from problem_bridge.workbench import confirm_problem, load_problem


PROJECT = "dyad-test"


def setup(tmp_path):
    root = tmp_path / "workspace"
    current = confirm_problem(root, PROJECT, {"question": "Summarize the synthetic records",
        "desired_change": "Each site has equal weight"})
    return root, current


def state(root, current):
    return dyad.handoff_state(root, current, load_problem(root, current, PROJECT))


def reply(root, current, **kwargs):
    return dyad.recipient_reply(root, PROJECT, current, actor="B-01", understanding="Compare site means",
        proposal="Average within each site first", expected_revision=state(root, current)["history"]["revision"], **kwargs)


def response(root, current, **kwargs):
    before = state(root, current)
    return dyad.confirm_response(root, PROJECT, current, reply_id=before["reply"]["reply_id"], actor="A-01",
        answer="I agree with equal weighting per site", reason="Sites contribute different counts",
        next_action="B returns a two-site sample; A checks the mean", no_open_questions=True,
        expected_revision=before["history"]["revision"], **kwargs)


def review(root, current, role, status="ready", note=""):
    return dyad.acknowledge(root, PROJECT, current, role=role, actor=role + "-01", status=status, note=note,
                           expected_revision=state(root, current)["history"]["revision"])


def test_two_directions_keep_originals_separate_reviews_and_no_change_path(tmp_path):
    root, current = setup(tmp_path)
    before = (current / "problem_record.json").read_bytes()
    reply(root, current, questions="How to label missing data?")
    assert state(root, current)["pending"]
    assert not state(root, current)["acknowledgements"]
    with pytest.raises(ValueError, match="must respond"):
        review(root, current, "B")
    newer = response(root, current, remaining="Missing-data labels remain to be decided", status="partial")
    assert (current / "problem_record.json").read_bytes() == before
    record = load_problem(root, newer, PROJECT)
    assert record.question == load_problem(root, current, PROJECT).question
    assert record.revision == 2 and record.audit is None
    assert state(root, newer)["acknowledgements"]["A"]["status"] == "partial"
    assert "B" not in state(root, newer)["acknowledgements"]
    review(root, newer, "B", "discuss", "I still need the label rule")
    assert not state(root, newer)["both_ready"]
    text = (newer / "collaboration_brief_zh.md").read_text(encoding="utf-8")
    assert "How to label missing data?" in text and "Missing-data labels remain" in text
    reply(root, newer, questions="May I label missing values as unknown?")
    assert state(root, newer)["pending"] and not state(root, newer)["acknowledgements"]


def test_version_change_expires_acknowledgements_and_sample_checks(tmp_path):
    root, current = setup(tmp_path)
    selection = {"source_key": "desired_change", "quote": "Each site has equal weight"}
    current = confirm_requirements(root, PROJECT, current, {"select": [selection]}, confirmed=True, expected_revision=1)
    reply(root, current)
    newer = response(root, current)
    record = load_problem(root, newer, PROJECT)
    requirement = record.requirements[0]
    assert requirement.status == "needs_reconfirmation"
    latest = confirm_requirements(root, PROJECT, newer, {"select": [{**selection, "requirement_id": requirement.requirement_id}]},
                                  confirmed=True, expected_revision=record.revision)
    assert not state(root, latest)["acknowledgements"]
    review(root, latest, "A")
    review(root, latest, "B")
    assert state(root, latest)["both_ready"]
    dyad.save_sample(root, PROJECT, latest, actor="B-01", title="Synthetic two-site calculation",
                     content="site,mean\nNorth,10\nSouth,20\nAll,15\n", expected_revision=state(root, latest)["history"]["revision"])
    sample = state(root, latest)["samples"][0]
    dyad.check_sample(root, PROJECT, latest, sample_path=sample["evidence"]["path"], requirement_id=requirement.requirement_id,
        role="A", actor="A-01", result="met", method="Manual arithmetic", location="All row, mean column", note="(10+20)/2 = 15",
        expected_revision=0, expected_handoff_revision=state(root, latest)["history"]["revision"])
    assert current_trace(root, PROJECT, latest)["requirements"][0]["check"]["applicable"]
    (root / sample["evidence"]["path"]).write_text("Changed", encoding="utf-8")
    assert not current_trace(root, PROJECT, latest)["requirements"][0]["check"]["applicable"]
    with pytest.raises(ValueError, match="changed"):
        dyad.read_sample(root, sample)
    changed = confirm_problem(root, PROJECT, {"question": "A different task"}, previous=latest)
    assert not state(root, changed)["acknowledgements"]
    assert not state(root, changed)["samples"]
    assert current_trace(root, PROJECT, changed)["requirements"][0]["check"] is None
    with pytest.raises(ValueError, match="Stale"):
        review(root, latest, "B")


def test_saved_drafts_survive_reopen_but_do_not_count_as_a_reply(tmp_path):
    root, current = setup(tmp_path)
    dyad.save_draft(root, PROJECT, current, role="B", values={"understanding": "A draft"}, expected_revision=0)
    reopened = state(root, Path(str(current)))
    assert reopened["drafts"]["B"]["understanding"] == "A draft"
    assert reopened["reply"] is None and not reopened["acknowledgements"]
    with pytest.raises(ValueError, match="Stale"):
        dyad.recipient_reply(root, PROJECT, current, actor="B", understanding="Old form", expected_revision=0)
    with pytest.raises(ValueError, match="another project"):
        dyad.save_draft(root, "wrong-project", current, role="B", values={}, expected_revision=1)


def test_two_stale_browser_submissions_cannot_both_write(tmp_path):
    root, current = setup(tmp_path)
    def submit(_):
        try:
            dyad.recipient_reply(root, PROJECT, current, actor="B", understanding="One reading", expected_revision=0)
            return "saved"
        except ValueError:
            return "rejected"
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(submit, range(2)))
    assert sorted(results) == ["rejected", "saved"]
    assert state(root, current)["history"]["revision"] == 1


def test_failed_confirmation_keeps_reply_and_retry_is_possible(tmp_path, monkeypatch):
    root, current = setup(tmp_path)
    reply(root, current)
    real = dyad.confirm_problem
    monkeypatch.setattr(dyad, "confirm_problem", lambda *a, **k: (_ for _ in ()).throw(OSError("disk failure")))
    with pytest.raises(ValueError, match="not confirmed"):
        response(root, current)
    assert state(root, current)["pending"]
    assert state(root, current)["history"]["events"][-1]["kind"] == "response_failed"
    monkeypatch.setattr(dyad, "confirm_problem", real)
    newer = response(root, current)
    assert state(root, newer)["response"] and not state(root, newer)["pending"]


def test_committed_response_recovers_without_final_receipt(tmp_path, monkeypatch):
    root, current = setup(tmp_path)
    reply(root, current)
    real = dyad.Journal.append
    def fail_receipt(self, kind, *args, **kwargs):
        if kind == "response_confirmed":
            raise OSError("receipt unavailable")
        return real(self, kind, *args, **kwargs)
    monkeypatch.setattr(dyad.Journal, "append", fail_receipt)
    newer = response(root, current)
    assert state(root, newer)["response"]
    review(root, newer, "B")
    assert state(root, newer)["both_ready"]


def test_clearing_unknowns_requires_an_explicit_decision(tmp_path):
    root, current = setup(tmp_path)
    reply(root, current, questions="Unknown condition")
    before = state(root, current)
    with pytest.raises(ValueError, match="unresolved"):
        dyad.confirm_response(root, PROJECT, current, reply_id=before["reply"]["reply_id"], actor="A",
            answer="Okay", reason="Keep goal", next_action="Try a sample", expected_revision=1)
    assert state(root, current)["history"]["revision"] == 1
