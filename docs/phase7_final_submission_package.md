# Phase 7: Final Submission Package (TKGQA Navigation Agent)

This document defines the **final submission-ready packaging** of the TKGQA Hierarchical Navigation Agent system.

It converts the research codebase into a **reproducible, paper-ready, and benchmark-executable artifact**.

---

# 1. Submission Goal

We aim to package the system into a form suitable for:

- ACL / EMNLP / NeurIPS submission
- Reproducibility evaluation
- Open-source release

The final artifact must include:

✔ Code
✔ Experiments
✔ Paper (LaTeX)
✔ Configurations
✔ Results

---

# 2. Final Repository Structure

```
tkgqa0628/
├── tkgqa_skills/
│   ├── agent/
│   ├── policy/
│   ├── router/
│   └── navigator/
│
├── scripts/
│   ├── experiment_runner.py
│   ├── export_results.py
│   └── reproduce.sh
│
├── docs/
│   ├── phase4_experimental_design.md
│   ├── paper_draft.md
│   └── phase7_final_submission_package.md
│
├── results/
│   ├── baseline.json
│   ├── agent.json
│   ├── ablation.json
│
├── configs/
│   ├── default.yaml
│   ├── rl_config.yaml
│
├── paper/
│   ├── main.tex
│   ├── figures/
│   ├── tables/
│
└── README.md
```

---

# 3. Reproducibility Pipeline

## 3.1 Full Experiment Run

```bash
python scripts/experiment_runner.py
```

## 3.2 Full Training + Evaluation

```bash
bash scripts/reproduce.sh
```

This script should:

1. Build skill tree
2. Run baseline evaluation
3. Train policy (Phase 2–3)
4. Evaluate unified agent
5. Export results
```

---

# 4. Metrics to Report

## 4.1 Main Metrics

- Accuracy (EM / F1)
- Hit@K
- Navigation steps
- Retrieval depth

## 4.2 Learning Metrics

- Reward convergence
- Policy loss stability
- Trajectory success rate

## 4.3 Efficiency Metrics

- Avg tool calls per query
- Avg navigation depth
- Latency per query

---

# 5. Baseline Summary Table (Paper-ready)

| Model | Accuracy | Hit@3 | Steps | Notes |
|------|----------|-------|-------|------|
| Flat Retrieval | TBD | TBD | High | No structure |
| Heuristic Router | TBD | TBD | Medium | Rule-based |
| LLM-only | TBD | TBD | Low | No tools |
| Our Agent | TBD | TBD | Low | Hierarchical + RL |

---

# 6. Ablation Study

We remove components from unified system:

## A1: w/o Neural Policy
- Replace embedding scoring with uniform selection

## A2: w/o RL Optimization
- Disable PolicyOptimizer updates

## A3: w/o Hierarchy
- Flat retrieval only

## A4: w/o Temporal Signal
- Ignore time-aware routing

---

# 7. LaTeX Paper Build

## Compile Paper

```bash
cd paper/
pdflatex main.tex
```

## Required Figures

- system_architecture.pdf
- skill_tree.pdf
- trajectory_examples.pdf

---

# 8. Experiment Export Format

All results must be exported as JSON:

```json
{
  "model": "UnifiedAgent",
  "accuracy": 0.0,
  "hit@3": 0.0,
  "steps": 0.0
}
```

---

# 9. Final Checklist Before Submission

## Code
- [ ] Unified agent runs end-to-end
- [ ] No missing imports
- [ ] Deterministic seed available

## Experiments
- [ ] Baseline results generated
- [ ] Ablation results generated
- [ ] Full agent evaluated

## Paper
- [ ] Method section complete
- [ ] Experiments section complete
- [ ] Figures generated

## Reproducibility
- [ ] single-command reproduction script

---

# 10. Final Statement

This system constitutes a full-stack hierarchical navigation framework for TKGQA with:

- Skill-based decomposition
- Neural routing policy
- Reinforcement learning optimization
- Unified agent execution

---

# End of Phase 7
