from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ParagraphCandidate:
    score: int
    order: int
    page: int
    paragraph_id: str
    text: str


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def keyword_score(text: str, keywords: list[str]) -> int:
    lowered = text.lower()
    return sum(1 for keyword in keywords if keyword.lower() in lowered)


def iter_paragraphs(sections: dict[str, Any]) -> list[ParagraphCandidate]:
    candidates: list[ParagraphCandidate] = []
    order = 0
    for page in sections.get("pages", []):
        page_number = int(page.get("page") or 0)
        for paragraph in page.get("paragraphs", []):
            text = normalize(str(paragraph.get("text") or ""))
            if not text:
                continue
            candidates.append(
                ParagraphCandidate(
                    score=0,
                    order=order,
                    page=page_number,
                    paragraph_id=str(paragraph.get("id") or f"P{order:04d}"),
                    text=text,
                )
            )
            order += 1
    return candidates


def estimate_char_budget(max_input_chars: int, figure_count: int) -> int:
    figure_penalty = min(max(figure_count, 0) * 700, 24000)
    budget = int(max_input_chars * 0.55) - figure_penalty
    return max(24000, min(48000, budget))


def build_stage_text_pack(
    *,
    sections: dict[str, Any],
    stage_keywords: list[str],
    always_keywords: list[str],
    budget_chars: int,
) -> str:
    candidates = iter_paragraphs(sections)
    selected: list[ParagraphCandidate] = []
    selected_orders: set[int] = set()

    for candidate in candidates:
        if keyword_score(candidate.text, always_keywords) > 0:
            selected.append(candidate)
            selected_orders.add(candidate.order)

    scored = []
    for candidate in candidates:
        if candidate.order in selected_orders:
            continue
        score = keyword_score(candidate.text, stage_keywords)
        if score > 0:
            scored.append(
                ParagraphCandidate(
                    score=score,
                    order=candidate.order,
                    page=candidate.page,
                    paragraph_id=candidate.paragraph_id,
                    text=candidate.text,
                )
            )

    scored.sort(key=lambda item: (-item.score, item.order))
    selected.extend(scored)

    lines: list[str] = []
    used = 0
    for item in sorted(selected, key=lambda item: item.order):
        block = f"[Page {item.page}, {item.paragraph_id}] {item.text}"
        if used and used + len(block) + 2 > budget_chars:
            continue
        lines.append(block)
        used += len(block) + 2
        if used >= budget_chars:
            break

    return "\n\n".join(lines)
