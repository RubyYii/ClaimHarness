from pathlib import Path

import pandas as pd

from .schemas import ManuscriptSection


def load_manuscript(path: str | Path) -> list[ManuscriptSection]:
    manuscript_path = Path(path)
    lines = manuscript_path.read_text(encoding="utf-8").splitlines()
    sections: list[ManuscriptSection] = []
    current_name: str | None = None
    current_start_line: int | None = None
    current_lines: list[str] = []

    def flush_section() -> None:
        if current_name is None:
            return
        sections.append(
            ManuscriptSection(
                name=current_name,
                text="\n".join(current_lines).strip(),
                start_line=current_start_line,
            )
        )

    for line_number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("#"):
            heading = stripped.lstrip("#").strip()
            if heading:
                flush_section()
                current_name = heading
                current_start_line = line_number
                current_lines = []
                continue
        if current_name is not None:
            current_lines.append(line)

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
