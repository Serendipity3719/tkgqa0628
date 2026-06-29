# Title
Hierarchical Skill-Based Navigation with Reinforcement Learning for Temporal Knowledge Graph Question Answering (TKGQA)

---

# Abstract
We propose a hierarchical navigation framework for Temporal Knowledge Graph Question Answering (TKGQA), where queries are resolved through structured skill decomposition and learned navigation policies. Unlike prior work relying on flat retrieval or pure language model reasoning, our system introduces a multi-layer skill abstraction, a neural navigation policy, and a reinforcement learning-based optimization loop. The agent operates over a skill tree materialized from the knowledge corpus and learns to navigate via trajectory-level rewards. Experimental design includes baselines, ablations, and navigation efficiency metrics.

---

# 1. Introduction
Temporal Knowledge Graph Question Answering requires reasoning over structured entities, relations, and temporal constraints. Existing approaches often suffer from:

- Flat retrieval inefficiency
- Lack of structured decomposition
- Weak generalization on long-tail queries

We address these issues via a unified navigation framework that treats the knowledge base as a navigable skill space.

---

# 2. Method

## 2.1 Skill Abstraction Layer
We define a skill as a mapping:

Skill = (entity_set, relation_type, temporal_scope, doc_ids)

This transforms the knowledge corpus into structured navigation units.

---

## 2.2 Hierarchical Navigation
We construct a multi-level navigation process:

Query → Skill Router → Skill Tree → Skill Navigator → Documents

Each step progressively refines the search space.

---

## 2.3 Neural Navigation Policy
We introduce an embedding-based policy:

π(skill | query) = cosine(query_embedding, skill_embedding)

This enables soft selection over multiple candidate skills.

---

## 2.4 Reinforcement Learning Optimization
We define trajectories:

τ = (query, skill_path, retrieved_docs, reward)

We optimize policy parameters using REINFORCE-style updates:

∇J(θ) = E[log π(a|s) * (R - b)]

where b is a baseline reward.

---

# 3. Unified Agent
We unify all modules into a single agent:

- Router
- Neural Policy
- Navigator
- Replay Buffer
- Policy Optimizer

The agent performs both inference and learning.

---

# 4. Experiments

## 4.1 Baselines
- Flat retrieval
- Heuristic routing
- LLM-only reasoning

## 4.2 Metrics
- Accuracy (EM/F1)
- Hit@K
- Navigation steps
- Retrieval efficiency

## 4.3 Ablation
- w/o neural policy
- w/o RL optimization
- w/o hierarchy

---

# 5. Expected Results
We hypothesize:

1. Hierarchical navigation improves retrieval efficiency
2. Neural policy improves disambiguation
3. RL improves long-tail query performance

---

# 6. Contributions

- Skill-based decomposition of TKGQA
- Hierarchical navigation framework
- Neural + RL hybrid policy learning
- End-to-end unified navigation agent

---

# 7. Conclusion
We present a unified navigation-based paradigm for TKGQA that integrates structured decomposition, neural ranking, and reinforcement learning into a single agent framework.
