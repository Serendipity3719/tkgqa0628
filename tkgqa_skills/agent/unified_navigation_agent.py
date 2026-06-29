from typing import Dict, Any

class UnifiedNavigationAgent:
    """
    Phase 3: Unified Navigation Agent

    Integrates all previous layers into a single end-to-end system:

    - SkillRouter (Phase 1)
    - SkillNavigator (Phase 1.2/1.3)
    - NeuralNavigationPolicy (Phase 2.3)
    - PolicyOptimizer (Phase 2.2)
    - Trajectory Buffer (Phase 2.1)
    """

    def __init__(self, router, neural_policy, navigator, optimizer, buffer=None):
        self.router = router
        self.neural_policy = neural_policy
        self.navigator = navigator
        self.optimizer = optimizer
        self.buffer = buffer

    def act(self, query: str, context: Dict[str, Any]):
        routing_result = self.router.route(query)

        policy_out = self.neural_policy.soft_select(routing_result)
        top_skill = policy_out["top_skill"]

        nav_result = self.navigator.navigate(routing_result, query=query)

        trajectory = {
            "query": query,
            "top_skill": top_skill,
            "selected_skill": nav_result.selected_skill,
            "doc_ids": nav_result.doc_ids,
            "routing": {
                "entity": routing_result.entity_skills,
                "relation": routing_result.relation_skills,
                "temporal": routing_result.temporal_skills,
            },
        }

        if self.buffer is not None:
            self.buffer.add(trajectory)

        return trajectory

    def train(self, batch_size: int = 8):
        if self.optimizer is None or self.buffer is None:
            return {"status": "no_training_components"}

        batch = self.buffer.sample(batch_size)
        return self.optimizer.update(batch)

    def run_episode(self, query: str, context: Dict[str, Any]):
        traj = self.act(query, context)

        reward = 1.0 if traj.get("doc_ids") else 0.0
        traj["reward"] = reward

        return traj
