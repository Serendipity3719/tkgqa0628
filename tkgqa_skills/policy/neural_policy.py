from typing import Dict, List, Any
import math

class NeuralNavigationPolicy:
    """
    Phase 2.3: Neural Policy Layer (prototype)

    Converts routing signals into embedding-based skill ranking.
    This replaces hand-crafted weights with representation similarity.
    """

    def __init__(self, skill_registry: Dict, dim: int = 32):
        self.skill_registry = skill_registry
        self.dim = dim

        # pseudo skill embeddings (no torch dependency)
        self.skill_embeddings = {
            k: [math.sin(i + len(k)) * 0.1 for i in range(dim)]
            for k in skill_registry
        }

    def encode_query(self, routing_result) -> List[float]:
        vec = [0.0] * self.dim

        for e in routing_result.entity_skills:
            vec[0] += len(e) * 0.1

        for r in routing_result.relation_skills:
            vec[1] += len(r) * 0.1

        for t in routing_result.temporal_skills:
            vec[2] += 1.0

        norm = math.sqrt(sum(v * v for v in vec)) + 1e-6
        return [v / norm for v in vec]

    def score(self, query_vec: List[float], skill_vec: List[float]) -> float:
        dot = sum(q * s for q, s in zip(query_vec, skill_vec))
        qn = math.sqrt(sum(q * q for q in query_vec)) + 1e-6
        sn = math.sqrt(sum(s * s for s in skill_vec)) + 1e-6
        return dot / (qn * sn)

    def rank(self, routing_result) -> List[Dict[str, Any]]:
        qvec = self.encode_query(routing_result)

        results = []
        for skill, vec in self.skill_embeddings.items():
            results.append({
                "skill": skill,
                "score": self.score(qvec, vec)
            })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results

    def soft_select(self, routing_result, topk: int = 3) -> Dict[str, Any]:
        ranked = self.rank(routing_result)

        topk_skills = ranked[:topk]

        max_score = max(r["score"] for r in ranked) if ranked else 1.0

        probs = []
        total = 0.0

        for r in ranked:
            p = math.exp(r["score"] - max_score)
            probs.append((r["skill"], p))
            total += p

        probs = [(s, p / total) for s, p in probs] if total > 0 else []

        return {
            "topk": topk_skills,
            "distribution": probs,
            "top_skill": ranked[0]["skill"] if ranked else None
        }
