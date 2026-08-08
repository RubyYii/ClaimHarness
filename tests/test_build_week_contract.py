import csv
import json

import pytest

from claim_harness.capability_gate import CapabilityClaim, audit_capability_claims
from claim_harness.llm import (
    LLMProviderConfig,
    LLMProviderError,
    StructuredProviderResult,
    resolve_provider_config,
)
from problem_bridge.build_contract import (
    BUILD_CONTRACT_RUN_ARTIFACTS,
    BuildProposal,
    HANDOFF_FILES,
    generate_evidence_gated_build,
)
from problem_bridge.generator import build_alignment_package
from problem_bridge.writer import write_alignment_package


def _package():
    return build_alignment_package(
        "I want to evaluate whether AI can support quality inspection review while "
        "a qualified human keeps final pass or fail authority."
    )


def test_capability_gate_rejects_autonomy_and_unapproved_evidence():
    claims = [
        CapabilityClaim(
            claim_id="BC001",
            statement="The assistant can organize supplied notes for a reviewer.",
            evidence_refs=["workflow_map.md#Current Workflow"],
            risk_level="medium",
            rationale="The workflow artifact describes the review step.",
            safe_fallback="The assistant may organize supplied notes for a reviewer.",
        ),
        CapabilityClaim(
            claim_id="BC002",
            statement="The AI automatically approves every final quality decision.",
            evidence_refs=["human_in_loop_plan.md#Required Human Review"],
            risk_level="high",
            rationale="This is a deliberate unsafe proposal for the gate.",
            safe_fallback="The assistant may flag cases; a qualified human decides.",
        ),
        CapabilityClaim(
            claim_id="BC003",
            statement="The assistant can predict future outcomes from private records.",
            evidence_refs=["invented_source.md"],
            risk_level="low",
            rationale="The cited evidence does not belong to the package.",
            safe_fallback="The assistant must abstain when evidence is unavailable.",
        ),
        CapabilityClaim(
            claim_id="BC004",
            statement="The assistant recommends a clinical code from supplied records.",
            evidence_refs=["workflow_map.md#Current Workflow"],
            risk_level="high",
            rationale="This tests a high-stakes fallback boundary.",
            safe_fallback="The assistant diagnoses patients from supplied records.",
        ),
    ]

    decisions = audit_capability_claims(
        claims,
        allowed_evidence_refs={
            "workflow_map.md#Current Workflow",
            "human_in_loop_plan.md#Required Human Review",
        },
        human_boundaries=["A qualified human keeps final authority."],
    )

    assert [item.status for item in decisions] == [
        "weakly_supported",
        "overclaimed",
        "unsupported",
        "needs_human_review",
    ]
    assert decisions[1].action == "downgrade"
    assert "qualified human" in decisions[1].final_statement
    assert decisions[2].action == "abstain"
    assert decisions[2].final_statement == ""
    assert "qualified human must make the final decision" in decisions[3].final_statement


def test_mock_build_contract_writes_auditable_package(tmp_path):
    package = _package()
    write_alignment_package(package, tmp_path, project_id="project-build-week-test")

    result = generate_evidence_gated_build(
        package,
        tmp_path,
        provider_config=resolve_provider_config("mock"),
        project_id="project-build-week-test",
    )

    assert set(BUILD_CONTRACT_RUN_ARTIFACTS).issubset(
        {path.name for path in tmp_path.iterdir() if path.is_file()}
    )
    assert set(HANDOFF_FILES) == {
        path.name for path in (tmp_path / "codex_handoff").iterdir()
    }
    assert result.runtime_record["gpt_5_6_used"] is False
    assert result.runtime_record["contains_api_key"] is False
    with (tmp_path / "claim_decisions.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert {row["status"] for row in rows} == {
        "supported",
        "weakly_supported",
        "overclaimed",
    }
    events = [
        json.loads(line)
        for line in (tmp_path / "build_record.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [event["stage"] for event in events] == [
        "proposal_generated",
        "claims_evidence_gated",
        "codex_handoff_written",
    ]


def test_gpt56_build_contract_records_non_secret_runtime_evidence(tmp_path):
    package = _package()
    seed_dir = tmp_path / "seed"
    seed_dir.mkdir()
    write_alignment_package(package, seed_dir, project_id="project-seed")
    seed = generate_evidence_gated_build(
        package,
        seed_dir,
        provider_config=resolve_provider_config("mock"),
        project_id="project-seed",
    )
    out = tmp_path / "remote"
    out.mkdir()
    write_alignment_package(package, out, project_id="project-remote")
    config = LLMProviderConfig(
        provider="openai",
        api_key="secret-test-key",
        base_url="https://api.openai.com/v1",
        model="gpt-5.6",
        api_style="openai-responses",
    )

    def structured_stub(*args, **kwargs):
        return StructuredProviderResult(
            payload=seed.proposal.model_dump(mode="json"),
            provider="openai",
            api_style="openai-responses",
            model="gpt-5.6-sol",
            response_id="resp_build_week_test",
        )

    result = generate_evidence_gated_build(
        package,
        out,
        provider_config=config,
        project_id="project-remote",
        structured_caller=structured_stub,
    )

    runtime_text = (out / "gpt_5_6_runtime.json").read_text(encoding="utf-8")
    assert result.runtime_record["gpt_5_6_used"] is True
    assert result.runtime_record["model"] == "gpt-5.6-sol"
    assert result.runtime_record["response_id"] == "resp_build_week_test"
    assert result.runtime_record["endpoint_origin"] == "https://api.openai.com"
    assert "secret-test-key" not in runtime_text


def test_remote_build_contract_rejects_non_gpt56_model(tmp_path):
    package = _package()
    write_alignment_package(package, tmp_path, project_id="project-wrong-model")
    config = LLMProviderConfig(
        provider="openai",
        api_key="test-key",
        base_url="https://api.openai.com/v1",
        model="gpt-5.4-mini",
        api_style="openai-responses",
    )

    with pytest.raises(LLMProviderError, match="GPT-5.6"):
        generate_evidence_gated_build(
            package,
            tmp_path,
            provider_config=config,
            project_id="project-wrong-model",
        )


def test_remote_build_contract_rejects_non_openai_endpoint(tmp_path):
    package = _package()
    write_alignment_package(package, tmp_path, project_id="project-wrong-endpoint")
    config = LLMProviderConfig(
        provider="openai",
        api_key="test-key",
        base_url="https://example.com/v1",
        model="gpt-5.6",
        api_style="openai-responses",
    )

    with pytest.raises(LLMProviderError, match="official OpenAI API"):
        generate_evidence_gated_build(
            package,
            tmp_path,
            provider_config=config,
            project_id="project-wrong-endpoint",
        )


def test_build_proposal_rejects_duplicate_claim_ids(tmp_path):
    package = _package()
    write_alignment_package(package, tmp_path, project_id="project-duplicate-claims")
    result = generate_evidence_gated_build(
        package,
        tmp_path,
        provider_config=resolve_provider_config("mock"),
        project_id="project-duplicate-claims",
    )
    payload = result.proposal.model_dump(mode="json")
    payload["capability_claims"][1]["claim_id"] = payload["capability_claims"][0]["claim_id"]

    with pytest.raises(ValueError, match="claim IDs must be unique"):
        BuildProposal.model_validate(payload)
