from dataclasses import dataclass
from typing import List, Dict

from tkgqa_skills.routing.semantic_router import SemanticRouter

@dataclass
class RoutingResult:
    entity_skills: List[str]
    relation_skills: List[str]
    temporal_skills: List[str]
    scores: Dict[str, float]
    semantic_clusters: List[str]
    entity_candidates: List[str]
    relation_clusters: List[str]
    temporal_candidates: List[Dict[str, str]]
    routing_scores: Dict[str, float]

class SkillRouter:
    """Phase 3-compatible Skill Router for TKGQA."""

    def __init__(self, skill_registry: Dict = None, mode: str = "lexical", top_k: int = 3):
        self.skill_registry = skill_registry
        self.semantic_router = SemanticRouter(mode=mode, top_k=top_k)

    def extract_entities(self, query: str) -> List[str]:
        return self.semantic_router.extract_entity_candidates(query)

    def extract_relations(self, query: str) -> List[str]:
        return self.semantic_router.extract_relation_candidates(query)

    def extract_temporal(self, query: str) -> List[str]:
        return self.semantic_router.route(query).temporal_candidates

    def route(self, query: str) -> RoutingResult:
        semantic = self.semantic_router.route(query)
        temporal_skills = [
            item.get("value") or item.get("operator") or item.get("slice_id")
            for item in semantic.temporal_candidates
            if item.get("value") or item.get("operator") or item.get("slice_id")
        ]

        return RoutingResult(
            entity_skills=semantic.entity_candidates,
            relation_skills=semantic.relation_clusters,
            temporal_skills=temporal_skills,
            scores=semantic.routing_scores,
            semantic_clusters=semantic.semantic_clusters,
            entity_candidates=semantic.entity_candidates,
            relation_clusters=semantic.relation_clusters,
            temporal_candidates=semantic.temporal_candidates,
            routing_scores=semantic.routing_scores,
        )
