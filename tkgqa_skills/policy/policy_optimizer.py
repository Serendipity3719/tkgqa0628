from typing import List, Dict, Any
import math
import random

class PolicyOptimizer:
    """
    Phase 2.2: Policy Optimization Layer

    Upgrades Phase 2.1 pseudo-learning into REINFORCE-style optimization.

    Key idea:
    - treat navigation as stochastic policy π(skill | query)
    - optimize expected reward using trajectory samples
    """

    def __init__(self, policy, buffer):
        self.policy = policy
        self.buffer = buffer

    # -----------------------------
    # fake log-probability model
    # -----------------------------
    def compute_logprob(self, skill_score: float, temperature: float = 1.0) -> float:
        """Convert score into pseudo log-probability."""
        return skill_score / max(temperature, 1e-6)

    # -----------------------------
    # baseline estimation
    # -----------------------------
    def compute_baseline(self, trajectories: List[Dict[str, Any]]) -> float:
        if not trajectories:
            return 0.0
        return sum(t["reward"] for t in trajectories) / len(trajectories)

    # -----------------------------
    # REINFORCE-style update
    # -----------------------------
    def update(self, trajectories: List[Dict[str, Any]]) -> Dict[str, Any]:

        baseline = self.compute_baseline(trajectories)
        policy_loss = 0.0

        for t in trajectories:
            reward = t.get("reward", 0.0)
            advantage = reward - baseline

            # simulate chosen skill score impact
            top_skill = t.get("top_skill", "global")

            # get pseudo score from current policy weights
            skill_score = 0.0
            for k, w in self.policy.weights.items():
                skill_score += w

            logprob = self.compute_logprob(skill_score)

            policy_loss += -logprob * advantage

            # -----------------------------
            # pseudo gradient update
            # -----------------------------
            lr = 0.01 * advantage

            for k in self.policy.weights:
                # reinforce good trajectories
                self.policy.weights[k] += lr * 0.1

        avg_loss = policy_loss / max(len(trajectories), 1)

        return {
            "baseline": baseline,
            "policy_loss": avg_loss,
            "updated_weights": self.policy.weights
        }

    # -----------------------------
    # sample training step
    # -----------------------------
    def train_step(self, batch_size: int = 8) -> Dict[str, Any]:

        batch = self.buffer.sample(batch_size)

        if not batch:
            return {
                "status": "empty_buffer",
                "message": "No trajectories available"
            }

        return self.update(batch)
