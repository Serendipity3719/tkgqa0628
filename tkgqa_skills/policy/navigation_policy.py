from typing import Dict, List, Any, Optional
import math

from tkgqa_skills.policy.policy_schema import (
    BacktrackingStep,
    CrossSkillJump,
    DecisionTrace,
    DrilldownStep,
    PolicyDecision,
    PolicyInput,
    policy_input_from_routing,
    routing_result_to_dict,
)

class NavigationPolicy:
    """
    Phase 5: Navigation Policy Layer (NPL)

    This module produces navigation decisions over the skill tree. It does not
    read fact files; it returns a plan and a normalized trace for execution.
    """

    def __init__(self, skill_registry: Dict = None, inspect_k: int = 2):
        self.skill_registry = skill_registry or {}
        self.inspect_k = max(2, int(inspect_k or 2))

        # pseudo-learned weights (will be replaced by training later)
        self.weights = {
            "entity": 1.2,
            "relation": 1.0,
            "temporal": 0.8,
            "recency_bias": 0.3,
            "specificity": 0.5,
            "semantic_cluster": 1.0,
        }
        self.cluster_backtracking_count = 0

    def score_skill(self, skill_name: str, routing_result) -> float:
        """Compute soft score for a candidate skill."""

        skill = self.skill_registry.get(skill_name, {})

        score = 0.0

        # entity match
        if skill.get("entity") and routing_result.entity_skills:
            if skill["entity"] in routing_result.entity_skills:
                score += self.weights["entity"]

        # relation match
        if skill.get("relation_type") and routing_result.relation_skills:
            if skill["relation_type"] in routing_result.relation_skills:
                score += self.weights["relation"]

        # temporal match
        if skill.get("time_range") and routing_result.temporal_skills:
            score += self.weights["temporal"]

        # specificity bonus (smaller doc sets = more specific skill)
        doc_count = len(skill.get("doc_ids", []))
        if doc_count > 0:
            score += self.weights["specificity"] * (1.0 / math.log(doc_count + 2))

        return score

    def rank_skills(self, routing_result) -> List[Dict[str, Any]]:
        """Return ranked skill list."""

        results = []

        for skill_name in self.skill_registry:
            score = self.score_skill(skill_name, routing_result)
            results.append({
                "skill": skill_name,
                "score": score
            })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results

    def select_top_k(self, routing_result, k: int = 3) -> List[str]:
        ranked = self.rank_skills(routing_result)
        return [r["skill"] for r in ranked[:k]]

    def soft_route(self, routing_result) -> Dict[str, Any]:
        """
        Phase 2 key API:
        return distribution over skills instead of single path
        """

        ranked = self.rank_skills(routing_result)

        # softmax over scores
        max_score = max(r["score"] for r in ranked) if ranked else 1.0

        probs = []
        total = 0.0

        for r in ranked:
            p = math.exp(r["score"] - max_score)
            probs.append((r["skill"], p))
            total += p

        probs = [(s, p / total) for s, p in probs] if total > 0 else []

        return {
            "ranked": ranked,
            "distribution": probs,
            "top_skill": ranked[0]["skill"] if ranked else None
        }

    def _routing_scores(self, routing_result) -> Dict[str, float]:
        routing = routing_result_to_dict(routing_result)
        return routing.get("routing_scores", {}) or routing.get("scores", {}) or {}

    def rank_semantic_clusters(self, routing_result) -> List[Dict[str, Any]]:
        """Rank semantic clusters by P(cluster | query)-style routing scores."""
        scores = self._routing_scores(routing_result)
        ranked = [
            {"semantic_cluster": cluster_id, "score": float(score)}
            for cluster_id, score in scores.items()
            if str(cluster_id).startswith("cluster_")
        ]
        ranked.sort(key=lambda r: (-r["score"], r["semantic_cluster"]))
        return ranked

    def select_semantic_clusters(self, routing_result, k: int = 2) -> List[str]:
        """Keep Top-K semantic clusters for drill-down and backtracking."""
        ranked = self.rank_semantic_clusters(routing_result)
        if ranked:
            return [r["semantic_cluster"] for r in ranked[:max(k, 2)]]

        clusters = []
        if isinstance(routing_result, dict):
            clusters = routing_result.get("semantic_clusters", [])
        else:
            clusters = getattr(routing_result, "semantic_clusters", [])
        return list(clusters[:max(k, 2)])

    def argmax_semantic_cluster(self, routing_result) -> Optional[str]:
        selected = self.select_semantic_clusters(routing_result, k=1)
        return selected[0] if selected else None

    def record_cluster_backtrack(self) -> int:
        self.cluster_backtracking_count += 1
        return self.cluster_backtracking_count

    def semantic_route(self, routing_result, k: int = 2) -> Dict[str, Any]:
        effective_k = max(k, self.inspect_k, 2)
        top_clusters = self.select_semantic_clusters(routing_result, k=effective_k)
        return {
            "top_semantic_clusters": top_clusters,
            "top_cluster": top_clusters[0] if top_clusters else None,
            "ranked_semantic_clusters": self.rank_semantic_clusters(routing_result),
            "inspect_k": effective_k,
            "policy": "semantic_npl_v1",
            "cluster_backtracking_count": self.cluster_backtracking_count,
        }

    def _as_policy_input(self, query_or_input, routing_result=None,
                         available_indexes: Dict[str, str] = None) -> PolicyInput:
        if isinstance(query_or_input, PolicyInput):
            return query_or_input
        if routing_result is None:
            routing = routing_result_to_dict(query_or_input)
            return policy_input_from_routing(routing.get("query", ""), routing, available_indexes)
        return policy_input_from_routing(str(query_or_input or ""), routing_result, available_indexes)

    def _cluster_scores(self, policy_input: PolicyInput) -> Dict[str, float]:
        routing = policy_input.semantic_routing_result
        scores = routing.get("routing_scores", {}) or routing.get("scores", {}) or {}
        return {
            str(cluster_id): float(score)
            for cluster_id, score in scores.items()
            if str(cluster_id).startswith("cluster_")
        }

    def select_clusters(self, policy_input: PolicyInput, inspect_k: int = None) -> List[str]:
        k = max(inspect_k or self.inspect_k, 2)
        scores = self._cluster_scores(policy_input)
        if scores:
            ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
            return [cluster_id for cluster_id, _score in ranked[:k]]
        clusters = policy_input.semantic_routing_result.get("semantic_clusters", [])
        return list(clusters[:k])

    def plan_drilldown(self, policy_input: PolicyInput,
                       selected_clusters: List[str]) -> List[DrilldownStep]:
        steps = [
            DrilldownStep(
                level="root",
                action="open_index",
                target=policy_input.available_indexes.get("root", "tkgqa/root/index.md"),
                rationale="Start from the root skill tree entry.",
            ),
            DrilldownStep(
                level="semantic_cluster",
                action="inspect_top_k",
                target=",".join(selected_clusters),
                rationale=f"Inspect at least {max(len(selected_clusters), self.inspect_k, 2)} semantic clusters by P(cluster | query).",
            ),
        ]
        if policy_input.entity_candidates:
            steps.append(DrilldownStep(
                level="entity",
                action="match_candidate",
                target=";".join(policy_input.entity_candidates[: self.inspect_k]),
                rationale="Bind entity candidates inside selected semantic cluster catalogs.",
            ))
        if policy_input.relation_candidates:
            steps.append(DrilldownStep(
                level="relation_family",
                action="match_candidate",
                target=";".join(policy_input.relation_candidates[: self.inspect_k]),
                rationale="Bind relation family candidates inside selected cluster relation_families.tsv.",
            ))
        if policy_input.temporal_candidates:
            temporal_targets = []
            for item in policy_input.temporal_candidates[: self.inspect_k]:
                if isinstance(item, dict):
                    temporal_targets.append(item.get("slice_id") or item.get("value") or item.get("operator") or str(item))
                else:
                    temporal_targets.append(str(item))
            steps.append(DrilldownStep(
                level="temporal_slice",
                action="select_slice",
                target=";".join(t for t in temporal_targets if t),
                rationale="Use temporal slice candidates before reading fact documents, except for global extrema.",
            ))
        steps.append(DrilldownStep(
            level="fact_doc",
            action="defer_execution",
            target="policy_executor",
            rationale="Policy returns a plan only; navigator or agent executes file reads.",
        ))
        return steps

    def plan_backtracking(self, policy_input: PolicyInput,
                          selected_clusters: List[str]) -> List[BacktrackingStep]:
        plan = []
        if len(selected_clusters) >= 2:
            plan.append(BacktrackingStep(
                trigger="cluster_branch_empty",
                action="inspect_next_cluster",
                target=selected_clusters[1],
                rationale="Always retain a second semantic cluster candidate before global fallback.",
            ))
        plan.extend([
            BacktrackingStep(
                trigger="entity_unmatched",
                action="try_next_entity_candidate",
                target="entity_candidates",
                rationale="Inspect alternate entity candidates inside the selected cluster catalog.",
            ),
            BacktrackingStep(
                trigger="relation_unmatched",
                action="try_related_relation_family",
                target="relation_families.tsv",
                rationale="Jump to related relation families before broad catalog search.",
            ),
            BacktrackingStep(
                trigger="temporal_slice_empty",
                action="inspect_adjacent_or_parent_slice",
                target="temporal_slices",
                rationale="Temporal drift may move evidence to an adjacent slice.",
            ),
            BacktrackingStep(
                trigger="global_extrema",
                action="use_full_entity_data",
                target="data.txt",
                rationale="First/last style tasks require global ordering across all slices.",
            ),
        ])
        return plan

    def plan_cross_skill_jumps(self, policy_input: PolicyInput,
                               selected_clusters: List[str]) -> List[CrossSkillJump]:
        jumps = []
        for src, dst in zip(selected_clusters, selected_clusters[1:]):
            jumps.append(CrossSkillJump(
                source=src,
                target=dst,
                reason="top-k semantic routing keeps related branch available for backtracking",
            ))
        if policy_input.temporal_candidates:
            jumps.append(CrossSkillJump(
                source="semantic_cluster",
                target="temporal_slices",
                reason="query contains temporal constraints; slice index can route to active entities",
            ))
        return jumps

    def termination_policy(self, policy_input: PolicyInput) -> str:
        return (
            "Terminate only after a grounded fact document is selected or after semantic cluster, entity, "
            "relation, and temporal backtracking plans are exhausted."
        )

    def plan(self, query_or_input, routing_result=None,
             available_indexes: Dict[str, str] = None,
             inspect_k: int = None) -> PolicyDecision:
        policy_input = self._as_policy_input(query_or_input, routing_result, available_indexes)
        effective_k = max(inspect_k or self.inspect_k, 2)
        selected_clusters = self.select_clusters(policy_input, inspect_k=effective_k)
        decision = PolicyDecision(
            selected_clusters=selected_clusters,
            cluster_scores=self._cluster_scores(policy_input),
            drilldown_plan=self.plan_drilldown(policy_input, selected_clusters),
            inspect_k=effective_k,
            backtracking_plan=self.plan_backtracking(policy_input, selected_clusters),
            cross_skill_jumps=self.plan_cross_skill_jumps(policy_input, selected_clusters),
            termination_policy=self.termination_policy(policy_input),
        )
        return decision

    def initialize_trace(self, policy_input: PolicyInput,
                         decision: PolicyDecision) -> DecisionTrace:
        inspected = {
            "semantic_clusters": decision.selected_clusters,
            "entities": policy_input.entity_candidates[:decision.inspect_k],
            "relations": policy_input.relation_candidates[:decision.inspect_k],
            "temporal": [
                item.get("slice_id") or item.get("value") or item.get("operator") if isinstance(item, dict) else str(item)
                for item in policy_input.temporal_candidates[:decision.inspect_k]
            ],
        }
        return DecisionTrace(
            query=policy_input.query,
            top_clusters=decision.selected_clusters,
            inspected_candidates=inspected,
            selected_entity=inspected["entities"][0] if inspected["entities"] else None,
            selected_relation_family=inspected["relations"][0] if inspected["relations"] else None,
            selected_temporal_slice=inspected["temporal"][0] if inspected["temporal"] else None,
            cross_skill_jumps=[jump.as_dict() for jump in decision.cross_skill_jumps],
            inspect_k=decision.inspect_k,
        )

    def decide(self, query_or_input, routing_result=None,
               available_indexes: Dict[str, str] = None,
               inspect_k: int = None) -> Dict[str, Any]:
        policy_input = self._as_policy_input(query_or_input, routing_result, available_indexes)
        decision = self.plan(policy_input, available_indexes=available_indexes, inspect_k=inspect_k)
        trace = self.initialize_trace(policy_input, decision)
        return {
            "policy_input": policy_input.as_dict(),
            "decision": decision.as_dict(),
            "trace": trace.as_dict(),
        }
