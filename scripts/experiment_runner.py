from typing import Dict, Any, List
import random
import statistics

"""
Phase 5: Experiment Execution

This script runs full-system evaluation for TKGQA Navigation Agent.
It supports:
- Baselines
- Unified Agent evaluation
- Metric aggregation
"""

# -----------------------------
# Mock dataset loader
# -----------------------------
def load_dataset(n: int = 50) -> List[Dict[str, Any]]:
    """Simulated TKGQA dataset."""
    dataset = []
    for i in range(n):
        dataset.append({
            "query": f"query_{i}",
            "gold_doc": f"doc_{random.randint(0, 20)}"
        })
    return dataset

# -----------------------------
# Baseline systems
# -----------------------------
class FlatRetrievalBaseline:
    def run(self, query: str):
        return {
            "doc_ids": [f"doc_{random.randint(0, 20)}" for _ in range(3)]
        }

class HeuristicBaseline:
    def run(self, query: str):
        return {
            "doc_ids": [f"doc_{len(query) % 20}"]
        }

# -----------------------------
# Evaluation metrics
# -----------------------------
def hit_at_k(pred_docs: List[str], gold: str, k: int = 3) -> float:
    return 1.0 if gold in pred_docs[:k] else 0.0

# -----------------------------
# Experiment Runner
# -----------------------------
class ExperimentRunner:
    def __init__(self, agent=None):
        self.agent = agent
        self.flat = FlatRetrievalBaseline()
        self.heuristic = HeuristicBaseline()

    def evaluate_system(self, system, dataset):
        scores = []

        for item in dataset:
            result = system.run(item["query"])
            score = hit_at_k(result["doc_ids"], item["gold_doc"])
            scores.append(score)

        return {
            "accuracy": statistics.mean(scores),
            "std": statistics.pstdev(scores) if len(scores) > 1 else 0.0
        }

    def evaluate_agent(self, dataset):
        scores = []

        for item in dataset:
            traj = self.agent.act(item["query"], context={})
            score = hit_at_k(traj.get("doc_ids", []), item["gold_doc"])
            scores.append(score)

        return {
            "accuracy": statistics.mean(scores),
            "std": statistics.pstdev(scores) if len(scores) > 1 else 0.0
        }

    def run_all(self):
        dataset = load_dataset()

        results = {
            "flat": self.evaluate_system(self.flat, dataset),
            "heuristic": self.evaluate_system(self.heuristic, dataset),
            "agent": self.evaluate_agent(dataset) if self.agent else None,
        }

        return results

# -----------------------------
# Entry point
# -----------------------------
if __name__ == "__main__":
    runner = ExperimentRunner(agent=None)
    results = runner.run_all()

    print("=== Phase 5 Results ===")
    for k, v in results.items():
        print(k, v)
