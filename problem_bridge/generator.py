from .mock_profiles import (
    cultural_archive_profile,
    generic_profile,
    quality_inspection_profile,
    training_policy_profile,
)
from .schemas import AlignmentPackage


def detect_profile(problem_text: str) -> str:
    text = problem_text.casefold()
    if any(
        token in text
        for token in (
            "quality inspection",
            "inspection workflow",
            "defect",
            "pass/fail",
            "visual review",
            "reviewable inspection",
        )
    ):
        return "quality_inspection"
    if any(
        token in text
        for token in (
            "cultural archive",
            "archive interpretation",
            "catalog note",
            "metadata",
            "provenance",
            "expert interpretation",
        )
    ):
        return "cultural_archive"
    if any(
        token in text
        for token in (
            "training policy",
            "policy support",
            "policy source",
            "training content",
            "compliance guidance",
        )
    ):
        return "training_policy"
    return "generic"


def build_alignment_package(problem_text: str) -> AlignmentPackage:
    profile = detect_profile(problem_text)
    if profile == "quality_inspection":
        return quality_inspection_profile(problem_text)
    if profile == "cultural_archive":
        return cultural_archive_profile(problem_text)
    if profile == "training_policy":
        return training_policy_profile(problem_text)
    return generic_profile(problem_text)
