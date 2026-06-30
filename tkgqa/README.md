# Phase 2: Hierarchical Skill Directory

This directory introduces a **hierarchical navigation structure** for TKGQA Skill system.

## Core Design Principle
We replace flat retrieval:
```
catalog → grep → file
```
with hierarchical navigation:
```
root skill → cluster skill → entity skill → temporal skill → fact/doc
```

This ensures **logarithmic reduction of search space (O(log N))** at each navigation step.

---

## Directory Structure

### Entity Clusters
- org: organization entities
- person: person entities
- location: geographical entities

### Relation Clusters
- event: general events
- transaction: financial / exchange actions
- conflict: conflict / war / dispute events

### Temporal Clusters
- 2010–2024: yearly decomposition of knowledge

---

## Navigation Strategy
Each level in the hierarchy must:

1. Reduce search space
2. Refine semantic focus
3. Delegate to sub-skill layer

---

## Mapping from Old System
| Old System | New System |
|-----------|------------|
| catalog.tsv | entity_clusters |
| grep search | cluster routing |
| flat file retrieval | hierarchical drill-down |

---

## Goal
Enable **structured navigation over temporal knowledge graphs using skill decomposition**.
