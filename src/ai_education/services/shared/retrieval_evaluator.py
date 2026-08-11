"""Small deterministic ranking metrics used before changing retrieval infrastructure."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RetrievalMetrics:
    recall_at_k: float
    mean_reciprocal_rank: float
    citation_accuracy: float
    query_count: int


def evaluate_rankings(
    rankings: list[list[str]],
    expected: list[set[str]],
    *,
    k: int = 5,
) -> RetrievalMetrics:
    if len(rankings) != len(expected):
        raise ValueError("rankings 与 expected 数量不一致")
    if not rankings:
        return RetrievalMetrics(0.0, 0.0, 0.0, 0)
    recalls: list[float] = []
    reciprocal: list[float] = []
    citation_hits = 0
    citation_total = 0
    for ranked, relevant in zip(rankings, expected, strict=True):
        selected = ranked[:k]
        hits = relevant.intersection(selected)
        recalls.append(len(hits) / len(relevant) if relevant else 1.0)
        reciprocal.append(
            next((1.0 / index for index, item in enumerate(selected, 1) if item in relevant), 0.0)
        )
        citation_hits += sum(item in relevant for item in selected)
        citation_total += len(selected)
    return RetrievalMetrics(
        recall_at_k=round(sum(recalls) / len(recalls), 4),
        mean_reciprocal_rank=round(sum(reciprocal) / len(reciprocal), 4),
        citation_accuracy=round(citation_hits / citation_total, 4) if citation_total else 0.0,
        query_count=len(rankings),
    )
