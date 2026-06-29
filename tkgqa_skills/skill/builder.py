from typing import Dict
from tkgqa_skills.skill.schema import Skill
from tkgqa_skills.routing.router import RoutingResult


class SkillBuilder:
    """
    Phase 1.3: Skill Builder

    Converts routing signals into Knowledge Skill objects.
    This is the bridge from heuristic extraction → semantic skill abstraction.
    """

    def build(self, routing: RoutingResult) -> Skill:
        """Build a Skill object from router output."""

        entity = routing.entity_skills[0] if routing.entity_skills else None
        relation = routing.relation_skills[0] if routing.relation_skills else None
        time_range = routing.temporal_skills[0] if routing.temporal_skills else None

        return Skill(
            entity=entity,
            topic=None,
            time_range=time_range,
            relation_type=relation,
            subskills=[],
            doc_ids=[],
            index_path=None,
            nav_policy="phase1_builder_v1"
        )