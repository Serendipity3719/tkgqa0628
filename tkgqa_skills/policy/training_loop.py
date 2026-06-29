from typing import List, Dict, Any
import random

class TrajectoryBuffer:
    """Stores navigation trajectories for policy learning."""

    def __init__(self):
        self.buffer: List[Dict[str, Any]] = []

    def add(self, trajectory: Dict[str, Any]):
        self.buffer.append(trajectory)

    def sample(self, k: int = 8) -> List[Dict[str, Any]]:
        return random.sample(self.buffer, min(k, len(self.buffer)))


class RewardFunction:
    """
    Phase 2 reward design:
    - reward retrieval success
    - penalize long / unfocused navigation
    """

    def compute(self, trajectory: Dict[str, Any]) -> float:
        doc_ids = trajectory.get("doc_ids", [])
        routing = trajectory.get("routing_result", {})

        reward = 0.0

        # success signal
        if doc_ids and len(doc_ids) > 0:
            reward += 1.0

        # entity alignment bonus
        if routing.get("entity_skills") and len(routing.get("entity_skills", [])) > 0:
            reward += 0.5

        # relation bonus
        if routing.get("relation_skills"):
            reward += 0.3

        # penalty for overly broad retrieval
        if len(doc_ids) > 10:
            reward -= 0.2

        return reward


class PolicyTrainer:
    """
    Phase 2.1: Lightweight Policy Learning Loop

    NOTE: This is a pseudo-training loop (no gradients yet),
    designed for research prototyping.
    """

    def __init__(self, policy, navigator):
        self.policy = policy
        self.navigator = navigator
        self.buffer = TrajectoryBuffer()
        self.reward_fn = RewardFunction()

    def run_episode(self, query: str, routing_result) -> Dict[str, Any]:
        """One navigation episode."""

        # policy selects skills
        soft = self.policy.soft_route(routing_result)
        top_skill = soft["top_skill"]

        # navigator executes
        nav_result = self.navigator.navigate(routing_result, query=query)

        trajectory = {
            "query": query,
            "top_skill": top_skill,
            "selected_skill": nav_result.selected_skill,
            "doc_ids": nav_result.doc_ids,
            "routing_result": {
                "entity_skills": routing_result.entity_skills,
                "relation_skills": routing_result.relation_skills,
                "temporal_skills": routing_result.temporal_skills,
            },
        }

        reward = self.reward_fn.compute(trajectory)
        trajectory["reward"] = reward

        self.buffer.add(trajectory)

        return trajectory

    def update_policy(self):
        """
        Pseudo update rule (placeholder for RL / distillation).
        In real Phase 2.2, replace with REINFORCE or supervised ranking loss.
        """

        samples = self.buffer.sample()

        if not samples:
            return {"status": "empty_buffer"}

        avg_reward = sum(s["reward"] for s in samples) / len(samples)

        # simulate weight adjustment signal
        adjustment_signal = 0.01 * avg_reward

        # update pseudo-weights
        for k in self.policy.weights:
            self.policy.weights[k] += adjustment_signal * 0.1

        return {
            "avg_reward": avg_reward,
            "adjustment": adjustment_signal,
            "updated_weights": self.policy.weights
        }
