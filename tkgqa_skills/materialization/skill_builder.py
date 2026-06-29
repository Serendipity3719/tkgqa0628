from typing import Dict, List, Any
import os

class SkillBuilder:
    """
    Phase 1.4: Skill Tree Materialization Layer

    Converts registry + skill structures into physical files:
    - SKILL.md
    - INDEX.md
    - entity-level directory structure
    """

    def __init__(self, skill_registry: Dict, output_dir: str = "tkgqa_skills"):
        self.skill_registry = skill_registry
        self.output_dir = output_dir

    def build_skill_md(self, skill_name: str, skill: Dict) -> str:
        return f"""# Skill: {skill_name}

Type: {skill.get('type','unknown')}
Entity: {skill.get('entity')}
Relation: {skill.get('relation_type')}
Temporal: {skill.get('time_range')}

## Routing Keywords
{skill.get('routing_keywords', [])}

## Subskills
{skill.get('subskills', [])}

## Documents
{skill.get('doc_ids', [])}
"""

    def build_index_md(self, skill_name: str, skill: Dict) -> str:
        subskills = skill.get("subskills", [])
        docs = skill.get("doc_ids", [])

        return f"""# INDEX: {skill_name}

## Subskills
{subskills}

## Documents
{docs}

## Navigation Hint
- entity → relation → temporal drill-down
"""

    def materialize_skill(self, skill_name: str):
        skill = self.skill_registry.get(skill_name, {})

        skill_dir = os.path.join(self.output_dir, skill_name)
        os.makedirs(skill_dir, exist_ok=True)

        skill_md = self.build_skill_md(skill_name, skill)
        index_md = self.build_index_md(skill_name, skill)

        with open(os.path.join(skill_dir, "SKILL.md"), "w", encoding="utf-8") as f:
            f.write(skill_md)

        with open(os.path.join(skill_dir, "INDEX.md"), "w", encoding="utf-8") as f:
            f.write(index_md)

        return {
            "skill": skill_name,
            "path": skill_dir,
            "files": ["SKILL.md", "INDEX.md"]
        }

    def build_all(self):
        results = []
        for skill_name in self.skill_registry:
            results.append(self.materialize_skill(skill_name))
        return results
