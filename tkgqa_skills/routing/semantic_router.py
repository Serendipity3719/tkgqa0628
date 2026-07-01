import re
from dataclasses import asdict, dataclass
from typing import Dict, List, Tuple

from tkgqa_skills.routing.cluster_taxonomy import (
    SEMANTIC_CLUSTERS,
    combined_cluster_scores,
    normalize_scores,
    rank_cluster_scores,
    signal_match_score,
)
from tkgqa_skills.temporal.slice_schema import extract_temporal_candidates_structured


@dataclass
class SemanticRoutingResult:
    semantic_clusters: List[str]
    entity_candidates: List[str]
    relation_clusters: List[str]
    temporal_candidates: List[Dict[str, str]]
    routing_scores: Dict[str, float]
    raw_scores: Dict[str, float]

    def as_dict(self) -> Dict:
        return asdict(self)


class SemanticRouter:
    """Phase 3 semantic router driven entirely by cluster_taxonomy schema."""

    def __init__(self, mode: str = "lexical", top_k: int = 3):
        self.mode = mode
        self.top_k = top_k

    def extract_entity_candidates(self, query: str) -> List[str]:
        candidates = re.findall(r"\b([A-Z][A-Za-z]*(?:\s+[A-Z][A-Za-z]*)*)\b", query)
        return list(dict.fromkeys(c.strip() for c in candidates if c.strip()))

    def extract_relation_candidates(self, query: str) -> List[str]:
        hits: List[Tuple[str, float]] = []
        for cluster in SEMANTIC_CLUSTERS:
            for family in cluster.relation_family_hints:
                score = signal_match_score(query, [family], 1.0)
                if score > 0:
                    hits.append((family, score))
            for alias in cluster.relation_aliases or []:
                score = signal_match_score(query, [alias], 1.0)
                if score > 0:
                    hits.append((alias, score))
        ranked = sorted(hits, key=lambda item: (-item[1], item[0]))
        return list(dict.fromkeys(item[0] for item in ranked))

    def route(self, query: str) -> SemanticRoutingResult:
        entity_candidates = self.extract_entity_candidates(query)
        relation_candidates = self.extract_relation_candidates(query)
        temporal_candidates = extract_temporal_candidates_structured(query)

        raw_scores = combined_cluster_scores(query, self.mode, include_entity=True, include_relation=True)

        for entity in entity_candidates:
            for cid, score in combined_cluster_scores(entity, self.mode, include_entity=True,
                                                      include_relation=False).items():
                raw_scores[cid] = round(raw_scores.get(cid, 0.0) + score * 1.25, 4)

        for relation in relation_candidates:
            for cid, score in combined_cluster_scores(relation, self.mode, include_entity=False,
                                                      include_relation=True).items():
                raw_scores[cid] = round(raw_scores.get(cid, 0.0) + score * 1.5, 4)

        if temporal_candidates:
            temporal_boost = min(len(temporal_candidates), 3) * 0.15
            for cid in list(raw_scores):
                raw_scores[cid] = round(raw_scores[cid] + temporal_boost, 4)

        normalized = normalize_scores(raw_scores)
        ranked = rank_cluster_scores(normalized or raw_scores, top_k=self.top_k)
        semantic_clusters = [cluster.cluster_id for cluster, _score in ranked]

        return SemanticRoutingResult(
            semantic_clusters=semantic_clusters,
            entity_candidates=entity_candidates,
            relation_clusters=relation_candidates,
            temporal_candidates=temporal_candidates,
            routing_scores=normalized or raw_scores,
            raw_scores=raw_scores,
        )


def route_query(query: str, mode: str = "lexical", top_k: int = 3) -> Dict:
    return SemanticRouter(mode=mode, top_k=top_k).route(query).as_dict()
