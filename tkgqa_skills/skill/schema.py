from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Skill:
    """
    Phase 1.1: Knowledge Skill Schema

    A Skill is a semantic knowledge unit (NOT an action/tool).

    It represents a structured slice of temporal knowledge in TKGQA.
    """

    # core semantic fields
    entity: Optional[str] = None
    topic: Optional[str] = None
    time_range: Optional[str] = None
    relation_type: Optional[str] = None

    # hierarchical structure (future Phase 2)
    subskills: List[str] = None

    # grounding / retrieval links
    doc_ids: List[str] = None

    # navigation metadata (used later in policy learning)
    index_path: Optional[str] = None
    nav_policy: Optional[str] = None
