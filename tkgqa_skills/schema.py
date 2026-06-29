from dataclasses import dataclass
from typing import List, Optional, Tuple

@dataclass
class Skill:
    id: str
    entity: Optional[str] = None
    relation_type: Optional[str] = None
    topic: Optional[str] = None
    parent_skill: Optional[str] = None
    subskills: Optional[List[str]] = None
    time_range: Optional[Tuple[int, int]] = None
    doc_ids: Optional[List[str]] = None
    routing_keywords: Optional[List[str]] = None
    skill_md: Optional[str] = None
    index_md: Optional[str] = None

    def is_entity(self):
        return self.entity is not None

    def is_relation(self):
        return self.relation_type is not None

    def is_temporal(self):
        return self.time_range is not None
