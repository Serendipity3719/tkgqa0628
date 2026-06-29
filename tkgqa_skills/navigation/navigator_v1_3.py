from typing import Dict, List, Any
from dataclasses import dataclass

@dataclass
class NavigationResult:
    selected_skill: str
    doc_ids: List[str]
    trace: Dict[str, Any]

class SkillNavigatorV13:
    """
    Phase 1.3 Skill Tree Drill-down Navigator (non-destructive version)
    """

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

    def drill_down(self, skill_name: str, query: str) -> str:
        skill = self.skill_registry.get(skill_name, {})
        subskills = skill.get("subskills", [])

        if not subskills:
            return skill_name

        q = query.lower()
        best_skill = skill_name
        best_score = 0

        for s in subskills:
            score = 0
            if s.lower() in q:
                score += 3

            years_10_15 = any(str(y) in q for y in range(2010, 2016))
            years_16_20 = any(str(y) in q for y in range(2016, 2021))
            years_21_24 = any(str(y) in q for y in range(2021, 2025))

            if years_10_15 and "2010" in s:
                score += 2
            if years_16_20 and "2016" in s:
                score += 2
            if years_21_24 and "2021" in s:
                score += 2

            if score > best_score:
                best_score = score
                best_skill = s

        return best_skill

    def retrieve_docs(self, skill_name: str) -> List[str]:
        skill = self.skill_registry.get(skill_name, {})
        return skill.get("doc_ids", [])

    def navigate(self, routing_result, query: str = "") -> NavigationResult:
        root_skill = self.select_skill(routing_result)
        final_skill = self.drill_down(root_skill, query)
        docs = self.retrieve_docs(final_skill)

        trace = {
            "root_skill": root_skill,
            "final_skill": final_skill,
            "drill_down_applied": root_skill != final_skill,
            "policy": "entity > relation > temporal + hierarchical drill-down"
        }

        return NavigationResult(
            selected_skill=final_skill,
            doc_ids=docs,
            trace=trace
        )
