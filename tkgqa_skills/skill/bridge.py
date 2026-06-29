from typing import Dict
from tkgqa_skills.routing.router import SkillRouter, RoutingResult
from tkgqa_skills.skill.builder import SkillBuilder
from tkgqa_skills.skill.registry import SkillRegistry


class SkillPipeline:
    """
    Phase 1.3.2: End-to-end Skill pipeline

    Connects:
    Router → SkillBuilder → SkillRegistry
    """

    def __init__(self, router: SkillRouter, registry: SkillRegistry):
        self.router = router
        self.builder = SkillBuilder()
        self.registry = registry

    def process(self, query: str, skill_id: str = None):
        """Full pipeline: query → Skill object → registry"""

        # 1. extract signals
        routing: RoutingResult = self.router.route(query)

        # 2. build knowledge skill
        skill = self.builder.build(routing)

        # 3. register skill
        sid = skill_id or f"skill_{len(self.registry.all())}"
        self.registry.register(sid, skill)

        return {
            "skill_id": sid,
            "skill": skill,
            "routing": routing
        }