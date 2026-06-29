from typing import Dict, Optional
from tkgqa_skills.skill.schema import Skill


class SkillRegistry:
    """
    Phase 1.2: Skill Registry

    Stores Knowledge Skills as semantic units (NOT tool signals).

    This is the central memory layer for skill-based navigation.
    """

    def __init__(self):
        # key: skill_id, value: Skill
        self._skills: Dict[str, Skill] = {}

    def register(self, skill_id: str, skill: Skill) -> None:
        """Register a new knowledge skill."""
        self._skills[skill_id] = skill

    def get(self, skill_id: str) -> Optional[Skill]:
        """Retrieve a skill by id."""
        return self._skills.get(skill_id)

    def all(self) -> Dict[str, Skill]:
        """Return all registered skills."""
        return self._skills

    def size(self) -> int:
        """Return number of registered skills."""
        return len(self._skills)
