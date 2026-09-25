import time
from jarvis.memory.search.models import MatchReason, SearchQuery, SearchResult

from typing import Iterable

RRF_K = 60.0

def calculate_rrf_score(rank: int, k: float = RRF_K) -> float:
    """Computes standard Reciprocal Rank Fusion component: 1 / (k + rank)."""
    return 1.0 / (k + rank)


def reciprocal_rank_fusion(
    rankings: Iterable[Iterable[str]], k: int = 60
) -> list[tuple[str, float]]:
    """Fuse document ranks. Scores are not probabilities."""
    if k < 1:
        raise ValueError("k must be positive")
    scores: dict[str, float] = {}
    for ranking in rankings:
        unique = dict.fromkeys(ranking)
        for rank, resource_id in enumerate(unique, start=1):
            scores[resource_id] = scores.get(resource_id, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda item: (-item[1], item[0]))


def rerank_search_results(
    candidates: list[dict],
    query: SearchQuery,
    semantic_ranks: dict[int, int] | None = None,
    context_file_ids: set[int] | None = None,
    ambiguity_threshold: float = 0.04,
) -> tuple[list[SearchResult], bool, str | None]:
    """Reranks candidate files using Reciprocal Rank Fusion and capped heuristic bonuses.
    
    Returns (ranked_results, is_ambiguous, clarification_prompt).
    """
    if not candidates:
        return [], False, None

    now_ns = time.time_ns()
    one_day_ns = 86_400 * 1_000_000_000
    seven_days_ns = 7 * one_day_ns
    context_file_ids = context_file_ids or set()
    semantic_ranks = semantic_ranks or {}

    clean_query = query.text.strip().casefold()
    results: list[SearchResult] = []

    for rank, cand in enumerate(candidates, 1):
        file_id = cand["id"]
        name = cand["name"]
        name_norm = cand["name_norm"]
        stem = (cand.get("stem") or "").casefold()
        ext = (cand.get("extension") or "").casefold()
        mod_ns = cand.get("modified_ns") or 0
        last_opened = cand.get("last_opened_ns")
        open_count = cand.get("open_count") or 0
        reasons: list[str] = []

        # 1. Base Lexical RRF score
        score = calculate_rrf_score(rank)
        reasons.append(MatchReason.PATH_MATCH.value)

        # 2. Semantic RRF score if present
        if file_id in semantic_ranks:
            sem_rank = semantic_ranks[file_id]
            score += calculate_rrf_score(sem_rank)
            reasons.append(MatchReason.SEMANTIC_MATCH.value)

        # 3. Exact name / stem match bonus (capped at +0.35)
        if clean_query == name_norm or clean_query == stem:
            score += 0.35
            reasons.append(MatchReason.EXACT_NAME.value)
        elif name_norm.startswith(clean_query) or stem.startswith(clean_query):
            score += 0.20
            reasons.append(MatchReason.NAME_PREFIX.value)

        # 4. Type match bonus (capped at +0.15)
        if query.type_hint:
            clean_type = query.type_hint.casefold()
            if ext == clean_type or (clean_type == "[directory]" and cand.get("is_directory")):
                score += 0.15
                reasons.append(MatchReason.TYPE_MATCH.value)
            elif ext != clean_type:
                # Penalty for mismatched explicit extension
                score *= 0.20

        # 4b. Directory hint bonus & filtering
        if query.directory_hint:
            dir_clean = query.directory_hint.casefold()
            cand_path = (cand.get("path") or "").casefold()
            if dir_clean in cand_path:
                score += 0.35
                reasons.append(MatchReason.PATH_MATCH.value)
            else:
                score *= 0.10

        # 5. Recency bonus
        age_ns = max(0, now_ns - mod_ns)
        if query.latest or (query.temporal_hint and ("latest" in query.temporal_hint or "recent" in query.temporal_hint)):
            if age_ns < one_day_ns:
                score += 0.25
                reasons.append(MatchReason.RECENT.value)
        elif query.temporal_hint and "yesterday" in query.temporal_hint:
            if one_day_ns * 0.5 <= age_ns <= one_day_ns * 2.0:
                score += 0.30
                reasons.append(MatchReason.RECENT.value)
        elif query.temporal_hint and "week" in query.temporal_hint:
            if seven_days_ns * 0.5 <= age_ns <= seven_days_ns * 1.5:
                score += 0.30
                reasons.append(MatchReason.RECENT.value)
        elif age_ns < one_day_ns:
            score += 0.10
            reasons.append(MatchReason.RECENT.value)
        elif age_ns < seven_days_ns:
            score += 0.05
            reasons.append(MatchReason.RECENT.value)

        # 6. Usage bonus (bounded, max +0.10)
        if open_count > 0:
            usage_boost = min(0.10, open_count * 0.02)
            score += usage_boost
            reasons.append(MatchReason.USAGE_BOOST.value)

        # 7. Context bonus (max +0.15)
        if file_id in context_file_ids:
            score += 0.15
            reasons.append(MatchReason.CONTEXT_REFERENCE.value)

        # Content match indicator
        if cand.get("is_content_match"):
            reasons.append(MatchReason.CONTENT_MATCH.value)

        # Calibrate confidence into [0.0, 1.0] range
        confidence = min(1.0, max(0.1, score / 0.65))

        results.append(
            SearchResult(
                file_id=file_id,
                path=cand["path"],
                name=name,
                extension=ext,
                score=score,
                confidence=confidence,
                match_reasons=sorted(set(reasons)),
                modified_ns=mod_ns,
                last_opened_ns=last_opened,
                source_signals={"open_count": open_count, "rank": rank},
                excerpt=cand.get("excerpt"),
            )
        )

    # Sort results descending by score
    results.sort(key=lambda r: r.score, reverse=True)

    # Check for Ambiguity
    is_ambiguous = False
    clarification = None
    if len(results) >= 2:
        top1 = results[0]
        top2 = results[1]
        score_diff = abs(top1.score - top2.score)
        if score_diff < ambiguity_threshold and top1.path != top2.path:
            is_ambiguous = True
            if top1.name == top2.name:
                clarification = f"I found multiple files named '{top1.name}'. Which one would you like?"
            else:
                clarification = f"I found '{top1.name}' and '{top2.name}'. Which one would you like?"

    return results, is_ambiguous, clarification
