from .mock_profiles import (
    chinese_painting_profile,
    generic_profile,
    hsg_profile,
    political_education_profile,
)
from .schemas import AlignmentPackage


def detect_profile(problem_text: str) -> str:
    text = problem_text.casefold()
    if any(token in text for token in ("hsg", "hysterosalpingography", "tubal", "obstruction")):
        return "hsg"
    if any(
        token in text
        for token in (
            "chinese painting",
            "painting commentary",
            "brushwork",
            "blank space",
            "vlm",
            "cultural interpretation",
        )
    ):
        return "chinese_painting"
    if any(
        token in text
        for token in (
            "political theory",
            "ideological",
            "value risk",
            "political education",
            "curriculum",
        )
    ):
        return "political_education"
    return "generic"


def build_alignment_package(problem_text: str) -> AlignmentPackage:
    profile = detect_profile(problem_text)
    if profile == "hsg":
        return hsg_profile(problem_text)
    if profile == "chinese_painting":
        return chinese_painting_profile(problem_text)
    if profile == "political_education":
        return political_education_profile(problem_text)
    return generic_profile(problem_text)
