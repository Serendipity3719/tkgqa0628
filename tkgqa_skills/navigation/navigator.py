from typing import Dict, List, Any
from dataclasses import dataclass

@dataclass
class NavigationResult:
    selected_skill: str
    doc_ids: List[str]
    trace: Dict[str, Any]

class SkillNavigator:
    """Phase 1.2 Skill Navigator for TKGQA"""

    def __init__(self, skill_registry: Dict):
        self.skill_registry = skill_registry

    def select_skill(self, routing_result) -> str:
        if routing_result.entity_skills:
            return routing_result.entity_skills[0]
        if routing_result.relation_skills:
            return routing_result.relation_skills[0]
        if routing_result.temporal_skills:
            return routing_result.temporal_skills[0]
        return "global"

    def retrieve_docs(self, skill_name: str) -> List[str]:
        skill = self.skill_registry.get(skill_name, {})
        return skill.get("doc_ids", [])

    def navigate(self, routing_result) -> NavigationResult:
        skill = self.select_skill(routing_result)
        docs = self.retrieve_docs(skill)

        trace = {
            "selected_skill": skill,
            "hit": skill in self.skill_registry,
            "policy": "entity > relation > temporal"
        }

        return NavigationResult(
            selected_skill=skill,
            doc_ids=docs,
            trace=trace
        )
