# NG-Layer Step 1 (RESTORED)

from dataclasses import dataclass, field
from typing import Dict, List, Any
import re


@dataclass
class Node:
    id: str
    type: str
    attrs: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Edge:
    src: str
    dst: str
    type: str
    weight: float = 1.0


@dataclass
class NavigationGraph:
    nodes: Dict[str, Node] = field(default_factory=dict)
    edges: List[Edge] = field(default_factory=list)

    def add_node(self, node: Node):
        self.nodes[node.id] = node

    def add_edge(self, edge: Edge):
        self.edges.append(edge)

    def neighbors(self, node_id: str):
        return [e.dst for e in self.edges if e.src == node_id]


def extract_entities(q: str):
    return list(set(re.findall(r"\b[A-Z][a-z]+\b", q)))


def extract_time(q: str):
    ql = q.lower()
    out = []
    if "before" in ql:
        out.append("before")
    if "after" in ql:
        out.append("after")
    return out


def build_graph(q: str):
    g = NavigationGraph()

    g.add_node(Node("q", "question", {"text": q}))

    for i, e in enumerate(extract_entities(q)):
        g.add_node(Node(f"e{i}", "entity", {"name": e}))
        g.add_edge(Edge("q", f"e{i}", "has_entity"))

    for i, t in enumerate(extract_time(q)):
        g.add_node(Node(f"t{i}", "time", {"signal": t}))
        g.add_edge(Edge("q", f"t{i}", "has_time"))

    return g