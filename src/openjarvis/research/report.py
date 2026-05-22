"""Research report rendering."""

from __future__ import annotations

import time

from openjarvis.research.models import Citation, ResearchReport


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class ResearchReportBuilder:
    """Render notes, summary, citations, and unresolved questions."""

    def build(
        self,
        *,
        report_id: str,
        question: str,
        summary: str,
        notes: list[str],
        citations: list[Citation],
        unresolved_questions: list[str],
        metadata: dict,
    ) -> ResearchReport:
        title = f"Research Report: {question[:72]}"
        body = self._body(
            question=question,
            summary=summary,
            notes=notes,
            citations=citations,
            unresolved_questions=unresolved_questions,
        )
        return ResearchReport(
            id=report_id,
            question=question,
            title=title,
            notes=notes,
            summary=summary,
            citations=citations,
            unresolved_questions=unresolved_questions,
            body=body,
            created_at=_utc_now(),
            metadata=metadata,
        )

    def _body(
        self,
        *,
        question: str,
        summary: str,
        notes: list[str],
        citations: list[Citation],
        unresolved_questions: list[str],
    ) -> str:
        lines = [
            f"# Research Report: {question}",
            "",
            "## Summary",
            summary,
            "",
            "## Notes",
        ]
        lines.extend(f"- {note}" for note in notes)
        if not notes:
            lines.append("- No source-backed notes were extracted yet.")
        lines.extend(["", "## Citations"])
        lines.extend(
            (
                f"- {citation.label} {citation.title} "
                f"({citation.url or 'cached local source'}), "
                f"accessed {citation.access_date}"
            )
            for citation in citations
        )
        if not citations:
            lines.append("- No citations available.")
        lines.extend(["", "## Unresolved Questions"])
        lines.extend(f"- {question}" for question in unresolved_questions)
        return "\n".join(lines).strip() + "\n"


__all__ = ["ResearchReportBuilder"]
