import re
from pathlib import Path

import pandas as pd

from .schemas import ManuscriptSection


def load_manuscript(path: str | Path) -> list[ManuscriptSection]:
    manuscript_path = Path(path)
    lines = manuscript_path.read_text(encoding="utf-8-sig").splitlines()
    if not any(line.strip() for line in lines):
        raise ValueError(f"Manuscript contains no text: {manuscript_path}")

    sections: list[ManuscriptSection] = []
    current_name: str | None = None
    current_start_line: int | None = None
    current_content_base = 1
    current_lines: list[str] = []
    current_source_kind = "manuscript"

    def flush_section(fallback_name: str | None = None) -> None:
        section_name = current_name or fallback_name
        if section_name is None:
            return

        nonblank_indexes = [index for index, line in enumerate(current_lines) if line.strip()]
        if nonblank_indexes:
            first_index = nonblank_indexes[0]
            last_index = nonblank_indexes[-1]
            section_text = "\n".join(current_lines[first_index : last_index + 1])
            content_start_line = current_content_base + first_index
        else:
            section_text = ""
            content_start_line = None

        sections.append(
            ManuscriptSection(
                name=section_name,
                text=section_text,
                start_line=current_start_line or content_start_line,
                content_start_line=content_start_line,
                source_kind=current_source_kind,
            )
        )

    for line_number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if re.search(
            r"<!--\s*provenance:\s*derived_text/ocr\b",
            stripped,
            flags=re.IGNORECASE,
        ):
            current_source_kind = "ocr"
            current_lines.append(line)
            continue
        if stripped.startswith("#"):
            heading = stripped.lstrip("#").strip()
            if heading:
                if current_name is None:
                    if any(item.strip() for item in current_lines):
                        flush_section("Preamble")
                else:
                    flush_section()
                if re.match(r"(?i)^source\s*:", heading):
                    # ProblemBridge source blocks may contain their own Markdown
                    # subheadings. Provenance persists through those headings
                    # and resets only when the next source block begins.
                    current_source_kind = "manuscript"
                current_name = heading
                current_start_line = line_number
                current_content_base = line_number + 1
                current_lines = []
                continue
        current_lines.append(line)

    if current_name is None:
        flush_section("Manuscript")
    else:
        flush_section()
    return sections


def load_tables(path: str | Path) -> dict[str, pd.DataFrame]:
    tables_path = Path(path)
    return {
        csv_path.stem: pd.read_csv(csv_path)
        for csv_path in sorted(tables_path.glob("*.csv"))
    }


def load_references(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8")
