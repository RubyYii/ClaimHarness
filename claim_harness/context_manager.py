from dataclasses import dataclass

import pandas as pd

from .schemas import ManuscriptSection


@dataclass(frozen=True)
class AuditContext:
    manuscript_sections: list[ManuscriptSection]
    tables: dict[str, pd.DataFrame]
    references: str


def build_context(
    manuscript_sections: list[ManuscriptSection],
    tables: dict[str, pd.DataFrame],
    references: str,
) -> AuditContext:
    return AuditContext(
        manuscript_sections=manuscript_sections,
        tables=tables,
        references=references,
    )
