from dataclasses import dataclass
from typing import List, Dict
import re

@dataclass
class RoutingResult:
    entity_skills: List[str]
    relation_skills: List[str]
    temporal_skills: List[str]
    scores: Dict[str, float]

class SkillRouter:
    """Phase 1 Skill Router for TKGQA"""

    def __init__(self, skill_registry: Dict):
        self.skill_registry = skill_registry

    def extract_entities(self, query: str) -> List[str]:
        candidates = re.findall(r"\\b([A-Z][a-zA-Z]+(?:\\s[A-Z][a-zA-Z]+)*)\\b", query)
        return list(set(candidates))

    def extract_relations(self, query: str) -> List[str]:
        keywords = ["acquire","acquisition","merge","investment","conflict","war","trade","agreement","sanction","appoint","resign"]
        q = query.lower()
        return [k for k in keywords if k in q]

    def extract_temporal(self, query: str) -> List[str]:
        years = re.findall(r"(19\\d{2}|20\\d{2})", query)
        out = []
        for y in years:
            yr = int(y)
            if yr <= 2015:
                out.append("2010_2015")
            elif yr <= 2020:
                out.append("2016_2020")
            else:
                out.append("2021_2024")
        return list(set(out))

    def route(self, query: str) -> RoutingResult:
        entities = self.extract_entities(query)
        relations = self.extract_relations(query)
        temporal = self.extract_temporal(query)

        scores = {
            "entity_conf": 0.8 if entities else 0.3,
            "relation_conf": 0.7 if relations else 0.2,
            "temporal_conf": 0.6 if temporal else 0.2
        }

        return RoutingResult(
            entity_skills=entities,
            relation_skills=relations,
            temporal_skills=temporal,
            scores=scores
        )
