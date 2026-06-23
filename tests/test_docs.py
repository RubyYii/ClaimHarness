from pathlib import Path


README = Path("README.md")
DOCS = {
    "architecture": Path("docs/architecture.md"),
    "walkthrough": Path("docs/demo_walkthrough.md"),
    "limitations": Path("docs/limitations.md"),
}


def test_readme_contains_demo_quality_sections():
    text = README.read_text(encoding="utf-8")
    required_phrases = [
        "ClaimHarness: A Lightweight Agent Harness for Scientific Claim-Evidence Auditing",
        "ClaimHarness turns a scientific manuscript into an auditable claim-evidence package.",
        "```mermaid",
        "Task Spec",
        "Context Manager",
        "Claim Extractor",
        "Evidence Retriever",
        "Verifier",
        "Audit Package",
        "Why this is an Agent Harness",
        "This is not a prompt-only reviewer.",
        "agent_trace.jsonl",
        "Limitations",
    ]

    for phrase in required_phrases:
        assert phrase in text


def test_required_docs_files_exist_and_have_core_topics():
    for path in DOCS.values():
        assert path.exists(), f"Missing documentation file: {path}"
        assert path.read_text(encoding="utf-8").strip()

    architecture = DOCS["architecture"].read_text(encoding="utf-8")
    walkthrough = DOCS["walkthrough"].read_text(encoding="utf-8")
    limitations = DOCS["limitations"].read_text(encoding="utf-8")

    assert "Pipeline" in architecture
    assert "agent_trace.jsonl" in walkthrough
    assert "does not guarantee factual correctness" in limitations
    assert "biomedical claims require human review" in limitations
