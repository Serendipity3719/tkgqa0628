import csv
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from tkgqa_skills.policy.navigation_policy import NavigationPolicy
from tkgqa_skills.routing.cluster_taxonomy import cluster_for_id, semantic_cluster_dirname
from tkgqa_skills.routing.semantic_router import SemanticRouter


@dataclass
class NavigationResult:
    selected_skill: str
    doc_ids: List[str]
    trace: Dict[str, Any]
    routing_path: Dict[str, Optional[str]] = field(default_factory=dict)


class SkillNavigator:
    """Phase 3 Semantic Cluster Navigator for TKGQA."""

    def __init__(self, skill_registry: Dict = None, tkgqa_root: str = "tkgqa",
                 semantic_router: SemanticRouter = None, policy: NavigationPolicy = None):
        self.skill_registry = skill_registry or {}
        self.tkgqa_root = tkgqa_root
        self.semantic_router = semantic_router or SemanticRouter()
        self.policy = policy or NavigationPolicy(self.skill_registry)

    def _cluster_dir(self, cluster_id: str) -> str:
        cluster = cluster_for_id(cluster_id)
        return os.path.join(self.tkgqa_root, "semantic_clusters", semantic_cluster_dirname(cluster))

    def _read_tsv(self, path: str) -> List[Dict[str, str]]:
        if not os.path.isfile(path):
            return []
        rows: List[Dict[str, str]] = []
        with open(path, encoding="utf-8", newline="") as f:
            header = None
            for raw in f:
                line = raw.rstrip("\n\r")
                if not line:
                    continue
                if line.startswith("#"):
                    header = line[1:].split("\t")
                    continue
                parts = line.split("\t")
                if header and len(parts) == len(header):
                    rows.append(dict(zip(header, parts)))
                else:
                    rows.append({str(i): value for i, value in enumerate(parts)})
        return rows

    def _match_entity(self, cluster_dir: str, entity_candidates: List[str]) -> Optional[Dict[str, str]]:
        rows = self._read_tsv(os.path.join(cluster_dir, "catalog.tsv"))
        if not rows:
            return None
        if not entity_candidates:
            return rows[0]

        lowered = [(cand, cand.replace(" ", "_").lower()) for cand in entity_candidates]
        for row in rows:
            name = row.get("canonical_name", "")
            low_name = name.lower()
            for cand, low_cand in lowered:
                if low_cand and (low_cand == low_name or low_cand in low_name or low_name in low_cand):
                    return row
        return rows[0]

    def _match_relation(self, cluster_dir: str, relation_candidates: List[str]) -> Optional[Dict[str, str]]:
        rows = self._read_tsv(os.path.join(cluster_dir, "relation_families.tsv"))
        if not rows:
            return None
        if not relation_candidates:
            return rows[0]

        lowered = [r.replace(" ", "_").lower() for r in relation_candidates]
        for row in rows:
            family = row.get("family", "").lower()
            members = row.get("member_codes", "").lower()
            for rel in lowered:
                if rel and (rel == family or rel in family or rel in members):
                    return row
        return rows[0]

    def _temporal_leaf(self, cluster_dir: str, entity_row: Optional[Dict[str, str]],
                       temporal_candidates: List[Any]) -> Optional[str]:
        if not entity_row:
            return None
        entity_path = os.path.join(cluster_dir, entity_row.get("database_path", "").split("/")[-1])
        for candidate in temporal_candidates:
            if isinstance(candidate, dict):
                if candidate.get("type") == "global_extrema":
                    return None
                slice_id = candidate.get("slice_id")
                if slice_id:
                    leaf = os.path.join(entity_path, "temporal_slices", slice_id, "index.md")
                    if os.path.isfile(leaf):
                        return leaf.replace("\\", "/")
                value = candidate.get("value", "")
                if value.isdigit() and len(value) == 4:
                    leaf = os.path.join(entity_path, "temporal", value, "index.md")
                    if os.path.isfile(leaf):
                        return leaf.replace("\\", "/")
            elif isinstance(candidate, str) and candidate.isdigit() and len(candidate) == 4:
                leaf = os.path.join(entity_path, "temporal", candidate, "index.md")
                if os.path.isfile(leaf):
                    return leaf.replace("\\", "/")
        return None

    def _temporal_reason(self, temporal_candidates: List[Any], temporal_leaf: Optional[str]) -> Optional[str]:
        if not temporal_leaf:
            for candidate in temporal_candidates:
                if isinstance(candidate, dict) and candidate.get("type") == "global_extrema":
                    return candidate.get("reason")
            return None
        for candidate in temporal_candidates:
            if isinstance(candidate, dict):
                slice_id = candidate.get("slice_id")
                value = candidate.get("value")
                if (slice_id and slice_id in temporal_leaf) or (value and value in temporal_leaf):
                    return candidate.get("reason")
        return "temporal candidate matched available leaf"

    def _candidate_doc(self, entity_row: Optional[Dict[str, str]], temporal_leaf: Optional[str]) -> List[str]:
        if not entity_row:
            return []
        db_path = entity_row.get("database_path", "")
        if temporal_leaf:
            return [temporal_leaf]
        return [db_path]

    def _field(self, routing_result, dict_key: str, attr_key: str, default=None):
        if isinstance(routing_result, dict):
            return routing_result.get(dict_key, default)
        return getattr(routing_result, attr_key, default)

    def _build_path(self, cluster_id: str, cluster_dir: str, entity_row: Optional[Dict[str, str]],
                    relation_row: Optional[Dict[str, str]], temporal_leaf: Optional[str],
                    temporal_reason: Optional[str]) -> Dict[str, Optional[str]]:
        return {
            "semantic_cluster": semantic_cluster_dirname(cluster_for_id(cluster_id)),
            "entity_candidate": entity_row.get("canonical_name") if entity_row else None,
            "relation_cluster": relation_row.get("family") if relation_row else None,
            "temporal_leaf": temporal_leaf,
            "temporal_slice": temporal_leaf.split("/temporal_slices/")[1].split("/")[0]
            if temporal_leaf and "/temporal_slices/" in temporal_leaf else None,
            "temporal_reason": temporal_reason,
        }

    def navigate(self, query_or_routing_result, query: str = "") -> NavigationResult:
        if isinstance(query_or_routing_result, str):
            query = query_or_routing_result
            routing_result = self.semantic_router.route(query)
        else:
            routing_result = query_or_routing_result
            if not query:
                query = getattr(routing_result, "query", "")

        policy_decision = self.policy.semantic_route(routing_result, k=2)
        top_clusters = policy_decision["top_semantic_clusters"]

        entity_candidates = self._field(routing_result, "entity_candidates", "entity_candidates") or self._field(routing_result, "entity_skills", "entity_skills", [])
        relation_candidates = self._field(routing_result, "relation_clusters", "relation_clusters") or self._field(routing_result, "relation_skills", "relation_skills", [])
        temporal_candidates = self._field(routing_result, "temporal_candidates", "temporal_candidates") or self._field(routing_result, "temporal_skills", "temporal_skills", [])

        attempts = []
        selected_path = None
        selected_docs: List[str] = []
        selected_skill = "global_fallback"

        for idx, cluster_id in enumerate(top_clusters):
            if idx > 0:
                self.policy.record_cluster_backtrack()
            cluster_dir = self._cluster_dir(cluster_id)
            entity_row = self._match_entity(cluster_dir, entity_candidates)
            relation_row = self._match_relation(cluster_dir, relation_candidates)
            temporal_leaf = self._temporal_leaf(cluster_dir, entity_row, temporal_candidates)
            temporal_reason = self._temporal_reason(temporal_candidates, temporal_leaf)
            routing_path = self._build_path(cluster_id, cluster_dir, entity_row, relation_row,
                                            temporal_leaf, temporal_reason)
            docs = self._candidate_doc(entity_row, temporal_leaf)
            hit = bool(entity_row or relation_row or temporal_leaf)
            attempts.append({
                "cluster": cluster_id,
                "cluster_dir": cluster_dir.replace("\\", "/"),
                "hit": hit,
                "routing_path": routing_path,
                "doc_ids": docs,
            })
            if hit:
                selected_path = routing_path
                selected_docs = docs
                selected_skill = routing_path["semantic_cluster"]
                break

        if selected_path is None:
            selected_path = {
                "semantic_cluster": None,
                "entity_candidate": entity_candidates[0] if entity_candidates else None,
                "relation_cluster": relation_candidates[0] if relation_candidates else None,
                "temporal_leaf": temporal_candidates[0] if temporal_candidates else None,
                "temporal_slice": None,
                "temporal_reason": None,
            }

        trace = {
            "policy": "query -> semantic_cluster(top2) -> entity/relation/time -> drill_down",
            "query": query,
            "routing_scores": self._field(routing_result, "routing_scores", "routing_scores") or self._field(routing_result, "scores", "scores", {}),
            "top_semantic_clusters": top_clusters,
            "routing_path": selected_path,
            "attempts": attempts,
            "metrics": {
                "top_level_routing_accuracy": None,
                "semantic_cluster_hit": bool(attempts and attempts[0]["hit"]),
                "cluster_backtracking_count": self.policy.cluster_backtracking_count,
            },
            "fallback": selected_skill == "global_fallback",
        }

        return NavigationResult(
            selected_skill=selected_skill,
            doc_ids=selected_docs,
            trace=trace,
            routing_path=selected_path,
        )
