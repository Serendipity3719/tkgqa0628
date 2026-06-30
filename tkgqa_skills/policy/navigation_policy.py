from typing import Dict, List, Any, Optional
import math

class NavigationPolicy:
    """
    Phase 2: Navigation Policy Learning (initial version)

    This layer upgrades heuristic routing into a score-based policy module.

    Goal:
    - support multi-skill ranking
    - introduce soft selection (probabilistic routing)
    - prepare for learned policy replacement (RL / LLM)
    """

    def __init__(self, skill_registry: Dict):
        self.skill_registry = skill_registry

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
        if isinstance(routing_result, dict):
            return routing_result.get("routing_scores", {}) or routing_result.get("scores", {})
        return getattr(routing_result, "routing_scores", None) or getattr(routing_result, "scores", {}) or {}

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
        top_clusters = self.select_semantic_clusters(routing_result, k=k)
        return {
            "top_semantic_clusters": top_clusters,
            "top_cluster": top_clusters[0] if top_clusters else None,
            "ranked_semantic_clusters": self.rank_semantic_clusters(routing_result),
            "cluster_backtracking_count": self.cluster_backtracking_count,
        }
