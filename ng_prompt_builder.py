# -*- coding: utf-8 -*-
"""
NG-Layer Prompt Builder (Step 2 - Route B)
==========================================

Purpose:
- Convert NavigationGraph into LLM-readable structured context
- Provide graph-aware augmentation for agent_nav (non-invasive)
- Keep backward compatibility (optional module)

This is NOT a routing replacement.
It is a prompt enrichment layer.
"""

from typing import Dict, Any
from navigation_graph import NavigationGraph


def graph_to_structured_text(g: NavigationGraph) -> str:
    """
    Serialize NG graph into a compact structured prompt block.
    """

    lines = []
    lines.append("[NG-LAYER CONTEXT]")

    # nodes summary
    lines.append("")
    lines.append("Nodes:")
    for nid, node in g.nodes.items():
        if node.type == "question":
            lines.append(f"- Q: {node.attrs.get('text','')}")
        elif node.type == "entity":
            lines.append(f"- E: {node.attrs.get('name','')}")
        elif node.type == "time":
            lines.append(f"- T: {node.attrs.get('signal','')}")
        else:
            lines.append(f"- {node.type}: {node.id}")

    # edges summary
    lines.append("")
    lines.append("Edges:")
    for e in g.edges:
        lines.append(f"- {e.src} -> {e.dst} ({e.type})")

    return "\n".join(lines)


def build_ng_prompt(question: str, graph: NavigationGraph) -> str:
    """
    Build augmented prompt for LLM.

    This does NOT change agent logic.
    It only enriches input context.
    """

    graph_block = graph_to_structured_text(graph)

    prompt = f"""
You are a knowledge navigation agent.

Use both the question and structured NG context to decide which skill to use.

{graph_block}

[QUESTION]
{question}

Instructions:
- First decide relevant skill
- Then execute navigation commands
- Then produce FINAL answer
"""

    return prompt


def debug_print_prompt(question: str, graph: NavigationGraph):
    print(build_ng_prompt(question, graph))
