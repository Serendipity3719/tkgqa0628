from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class PolicyInput:
    query: str
    semantic_routing_result: Dict[str, Any]
    entity_candidates: List[str] = field(default_factory=list)
    relation_candidates: List[str] = field(default_factory=list)
    temporal_candidates: List[Any] = field(default_factory=list)
    available_indexes: Dict[str, str] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DrilldownStep:
    level: str
    action: str
    target: str
    rationale: str

    def as_dict(self) -> Dict[str, str]:
        return asdict(self)


@dataclass
class BacktrackingStep:
    trigger: str
    action: str
    target: str
    rationale: str

    def as_dict(self) -> Dict[str, str]:
        return asdict(self)


@dataclass
class CrossSkillJump:
    source: str
    target: str
    reason: str

    def as_dict(self) -> Dict[str, str]:
        return asdict(self)


@dataclass
class PolicyDecision:
    selected_clusters: List[str]
    cluster_scores: Dict[str, float]
    drilldown_plan: List[DrilldownStep]
    inspect_k: int
    backtracking_plan: List[BacktrackingStep]
    cross_skill_jumps: List[CrossSkillJump]
    termination_policy: str
    policy: str = "semantic_npl_v1"

    def as_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["drilldown_plan"] = [step.as_dict() for step in self.drilldown_plan]
        data["backtracking_plan"] = [step.as_dict() for step in self.backtracking_plan]
        data["cross_skill_jumps"] = [jump.as_dict() for jump in self.cross_skill_jumps]
        return data


@dataclass
class DecisionTrace:
    query: str
    top_clusters: List[str]
    inspected_candidates: Dict[str, List[str]] = field(default_factory=dict)
    selected_entity: Optional[str] = None
    selected_relation_family: Optional[str] = None
    selected_temporal_slice: Optional[str] = None
    backtrack_events: List[Dict[str, Any]] = field(default_factory=list)
    cross_skill_jumps: List[Dict[str, Any]] = field(default_factory=list)
    fallback_reason: Optional[str] = None
    policy: str = "semantic_npl_v1"
    inspect_k: int = 2

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


def routing_result_to_dict(routing_result: Any) -> Dict[str, Any]:
    if routing_result is None:
        return {}
    if isinstance(routing_result, dict):
        return dict(routing_result)
    if hasattr(routing_result, "as_dict"):
        return routing_result.as_dict()
    out = {}
    for key in (
        "semantic_clusters",
        "entity_candidates",
        "relation_clusters",
        "temporal_candidates",
        "routing_scores",
        "raw_scores",
        "entity_skills",
        "relation_skills",
        "temporal_skills",
        "scores",
    ):
        if hasattr(routing_result, key):
            out[key] = getattr(routing_result, key)
    return out


def policy_input_from_routing(query: str, routing_result: Any,
                              available_indexes: Dict[str, str] = None) -> PolicyInput:
    routing = routing_result_to_dict(routing_result)
    return PolicyInput(
        query=query or routing.get("query", ""),
        semantic_routing_result=routing,
        entity_candidates=routing.get("entity_candidates") or routing.get("entity_skills") or [],
        relation_candidates=routing.get("relation_clusters") or routing.get("relation_skills") or [],
        temporal_candidates=routing.get("temporal_candidates") or routing.get("temporal_skills") or [],
        available_indexes=available_indexes or {},
    )
