# Phase 4: Experimental & Paper Design (TKGQA Navigation Agent)

This document formalizes the experimental setup for the Unified Navigation Agent system.
It defines benchmarks, evaluation metrics, baselines, and ablation studies.

---

# 1. Task Definition

We define TKGQA as a **hierarchical navigation problem over temporal knowledge graphs**:

Given a query q, the agent must:

1. Extract structured signals (entity / relation / temporal)
2. Navigate a skill tree (Skill Router → Navigator → Policy)
3. Retrieve supporting documents (doc_ids)
4. Produce final answer from retrieved evidence

---

# 2. Evaluation Objectives

We evaluate the system along four axes:

## 2.1 Answer Accuracy
- Exact Match (EM)
- F1 score (token overlap)

## 2.2 Navigation Efficiency
- Avg steps to reach correct doc
- Search depth (tree depth used)

## 2.3 Retrieval Quality
- Recall@K (doc retrieval coverage)
- Precision@K

## 2.4 Policy Quality
- Entropy of skill distribution
- Stability across reruns

---

# 3. Baselines

We compare against:

## 3.1 Flat Retrieval
- Single-pass grep / embedding search

## 3.2 Heuristic Skill Router (Phase 1 only)
- rule-based routing without learning

## 3.3 Oracle Routing
- Perfect skill selection (upper bound)

## 3.4 LLM-only Reasoning
- No tool usage, direct QA generation

---

# 4. Ablation Studies

We isolate contributions of each module:

## A1: Remove Neural Policy
- Replace with uniform skill selection

## A2: Remove Policy Optimizer
- No trajectory learning

## A3: Remove Hierarchical Navigation
- Flat doc retrieval only

## A4: Remove Temporal Encoding
- Ignore time-aware skill routing

---

# 5. Key Metrics

## Navigation Metrics
- Average navigation depth
- Redundant steps per query

## Learning Metrics
- Reward convergence curve
- Policy loss stability

## System Metrics
- Latency per query
- Tool-call count per query

---

# 6. Experimental Protocol

## Dataset Split
- Train: 70%
- Validation: 10%
- Test: 20%

## Training Setup
- Episode-based RL simulation
- Replay buffer sampling
- Batch size: 8–32

## Evaluation
- 5 random seeds
- Report mean ± std

---

# 7. Expected Results Hypothesis

We hypothesize:

1. Hierarchical navigation > flat retrieval
2. Neural policy > heuristic routing
3. RL optimization improves long-tail queries
4. Temporal skills improve time-sensitive QA

---

# 8. System Diagram (Conceptual)

Query
  ↓
Skill Router
  ↓
Neural Policy
  ↓
Skill Navigator (Hierarchy)
  ↓
Policy Optimizer (Training)
  ↓
Doc Retrieval
  ↓
Answer Generation

---

# 9. Contribution Summary

This system proposes:

- Skill-based decomposition of TKGQA
- Hierarchical navigation over knowledge space
- Learned navigation policy over skill tree
- RL-style trajectory optimization

---

# End of Phase 4 Design
