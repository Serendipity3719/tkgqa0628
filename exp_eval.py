# -*- coding: utf-8 -*-
"""
exp_eval.py — TKG2Skill 实验评估模块
===================================================================
读 trace JSON (富 trace 或 legacy agent_nav_*.json 皆可), 产出范式有效性分析:

  1. Skill Routing Accuracy      —— Router 选对 skill 的比例 (+ 混淆矩阵)
  2. End-to-End QA Accuracy      —— 整链命中率 (overall + 分 qtype)
  3. Navigation Efficiency       —— avg steps / tool calls / evidence / backtracks
  4. Failure Taxonomy            —— routing / entity / relation / temporal / execution
  5. Pipeline Loss Decomposition —— 把总损耗拆给 Routing 段 vs Navigation 段 (核心: 验证范式)

失败归类是**确定性启发式** (可复现、可被人工/LLM 标注覆盖), 规则见 classify_failure。
用法:
    python exp_eval.py agent_nav_100.json
    python exp_eval.py agent_nav_100.json --out metrics_100.json --annotations anno.json
"""
import argparse, json, collections, sys
import exp_trace

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

TEMPORAL_QTYPES = {"after_first", "before_last", "before_after", "first_last"}
FAILURE_CATS = ["routing_error", "entity_resolution_error", "relation_error",
                "temporal_reasoning_error", "execution_error", "unknown"]


# ---- 失败归类 (仅对答错的题; 优先级有序的确定性规则) -----------------------
def classify_failure(trace):
    """返回 (category, evidence_str)。trace 必须答错才调用。"""
    nav, rt, ans = trace["navigation"], trace["routing"], trace["answer"]
    steps = nav["steps"]
    final = (ans.get("final") or "")

    any_err   = any(s["obs_error"] for s in steps)
    pivot_nf  = any("[pivot-not-found]" in (s["observation"] or "") for s in steps)
    ev_steps  = [s for s in steps if s["phase"] in ("evidence", "backtrack")]
    ev_found  = any((not s["obs_empty"]) and (not s["obs_error"]) for s in ev_steps)
    bind_steps = [s for s in steps if s["phase"] == "bind"]
    entity_bound = bool(nav["reconstructed_state"].get("D"))
    rel_bound    = bool(nav["reconstructed_state"].get("REL"))
    # catalog / relations grep 是否曾返回内容
    catalog_ok = any(("_catalog.tsv" in s["tool_call"]["cmd"]) and (not s["obs_empty"])
                     for s in bind_steps)
    relations_ok = any(("_relations.txt" in s["tool_call"]["cmd"]) and (not s["obs_empty"])
                       for s in bind_steps)
    gave_up = ("知识库中无相关事实" in final)
    broke   = any(m in final for m in ("[API_ERROR", "[无答案]", "[错误]")) or not final.strip()

    # 优先级 1: 执行层崩溃 (API/超时/根本没产出答案)
    if broke:
        return "execution_error", "run broke: empty/API_ERROR/no-FINAL"
    # 优先级 2: 路由错 (装错 skill)
    if rt["routing_observed"] and not rt["routing_correct"]:
        return "routing_error", f"loaded {rt['selected_skill']} != gold {rt['gold_skill']}"
    # 优先级 3: 没取到任何证据行 (放弃 or 全空)
    if not ev_found:
        if pivot_nf or not entity_bound or not catalog_ok:
            return "entity_resolution_error", "pivot/anchor never resolved (catalog/path)"
        if not rel_bound or not relations_ok:
            return "relation_error", "relation code never resolved"
        return "relation_error", "anchor bound but no evidence rows (likely wrong REL)"
    # 优先级 4: 取到了证据行却答错 (位置/粒度/方向/实体歧义)
    if trace["meta"]["gold_qtype"] in TEMPORAL_QTYPES or trace["meta"].get("answer_type") == "time":
        return "temporal_reasoning_error", "evidence found but wrong position/granularity"
    if any_err:
        return "execution_error", "tool errors on the evidence path"
    return "unknown", "wrong answer with evidence; needs manual review"


# ---- 指标聚合 --------------------------------------------------------------
def _mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else 0.0


def evaluate(traces, annotations=None):
    annotations = annotations or {}
    n = len(traces)
    # 先补 failure 分类
    for t in traces:
        if not t["answer"]["correct"]:
            quid = str(t["quid"])
            if quid in annotations:                       # 人工/LLM 标注覆盖启发式
                cat, ev = annotations[quid], "manual_annotation"
            else:
                cat, ev = classify_failure(t)
            t["failure"] = {"is_failure": True, "category": cat, "evidence": ev}

    # --- 1. Routing Accuracy ---
    routed = [t for t in traces if t["routing"]["routing_observed"]]
    routing_acc = _mean(t["routing"]["routing_correct"] for t in routed)
    confusion = collections.Counter(
        (t["routing"]["gold_skill"], t["routing"]["selected_skill"]) for t in routed)

    # --- 2. E2E Accuracy (overall + per qtype) ---
    e2e_acc = _mean(t["answer"]["correct"] for t in traces)
    per_qtype = {}
    by_qt = collections.defaultdict(list)
    for t in traces:
        by_qt[t["meta"]["gold_qtype"]].append(t)
    for qt, ts in sorted(by_qt.items()):
        per_qtype[qt] = {
            "n": len(ts),
            "acc": _mean(x["answer"]["correct"] for x in ts),
            "routing_acc": _mean(x["routing"]["routing_correct"]
                                 for x in ts if x["routing"]["routing_observed"]),
        }

    # --- 3. Navigation Efficiency (split correct / incorrect) ---
    def eff(ts):
        return {
            "avg_steps": _mean(x["navigation"]["num_steps"] for x in ts),
            "avg_tool_calls": _mean(x["navigation"]["num_tool_calls"] for x in ts),
            "avg_evidence_calls": _mean(x["navigation"]["num_evidence_calls"] for x in ts),
            "avg_backtracks": _mean(x["navigation"]["num_backtracks"] for x in ts),
        }
    correct_ts = [t for t in traces if t["answer"]["correct"]]
    wrong_ts   = [t for t in traces if not t["answer"]["correct"]]
    efficiency = {"all": eff(traces), "correct": eff(correct_ts), "incorrect": eff(wrong_ts)}

    # --- 4. Failure Taxonomy ---
    fail_counts = collections.Counter(t["failure"]["category"] for t in wrong_ts)
    failure_taxonomy = {c: fail_counts.get(c, 0) for c in FAILURE_CATS}
    fail_by_qtype = collections.defaultdict(lambda: collections.Counter())
    for t in wrong_ts:
        fail_by_qtype[t["meta"]["gold_qtype"]][t["failure"]["category"]] += 1

    # --- 5. Pipeline Loss Decomposition (验证范式: 损耗归因) ---
    # routing 段损耗 = 路由错的比例; navigation 段损耗 = 路由对里仍答错的比例
    routed_correct = [t for t in routed if t["routing"]["routing_correct"]]
    nav_acc_given_routing = _mean(t["answer"]["correct"] for t in routed_correct)
    decomposition = {
        "routing_loss": 1.0 - routing_acc,                       # 路由没选对
        "navigation_loss_given_correct_routing": 1.0 - nav_acc_given_routing,  # 选对了但导航丢
        "e2e_accuracy": e2e_acc,
        "note": "e2e ≈ routing_acc * nav_acc_given_routing (近似, 受 routing_mode 影响)",
    }

    return {
        "n": n,
        "routing_mode": traces[0]["meta"]["routing_mode"] if traces else None,
        "routing_accuracy": routing_acc,
        "routing_confusion": {f"{g}->{s}": c for (g, s), c in sorted(confusion.items())},
        "e2e_accuracy": e2e_acc,
        "per_qtype": per_qtype,
        "navigation_efficiency": efficiency,
        "failure_taxonomy": failure_taxonomy,
        "failure_by_qtype": {k: dict(v) for k, v in fail_by_qtype.items()},
        "pipeline_decomposition": decomposition,
    }


# ---- 报告打印 --------------------------------------------------------------
def print_report(m):
    p = lambda s="": print(s)
    p("=" * 64)
    p(f"TKG2Skill 实验评估   n={m['n']}   routing_mode={m['routing_mode']}")
    p("=" * 64)
    p(f"[1] Skill Routing Accuracy : {m['routing_accuracy']:.1%}")
    if m["routing_mode"] == "oracle":
        p("    ⚠ oracle 模式: qtype 已喂给 Agent, 该数字是路由上界, 非真实路由能力。")
    p(f"[2] End-to-End QA Accuracy : {m['e2e_accuracy']:.1%}")
    p("    per-qtype:")
    for qt, d in m["per_qtype"].items():
        p(f"      {qt:14s} n={d['n']:<4d} acc={d['acc']:.1%}  routing={d['routing_acc']:.1%}")
    p(f"[3] Navigation Efficiency  (steps / tool / evidence / backtrack)")
    for k in ("all", "correct", "incorrect"):
        e = m["navigation_efficiency"][k]
        p(f"      {k:10s} {e['avg_steps']:.1f} / {e['avg_tool_calls']:.1f} / "
          f"{e['avg_evidence_calls']:.1f} / {e['avg_backtracks']:.2f}")
    p(f"[4] Failure Taxonomy  (共 {sum(m['failure_taxonomy'].values())} 个失败)")
    for c, n in m["failure_taxonomy"].items():
        if n:
            p(f"      {c:26s} {n}")
    p(f"[5] Pipeline Loss Decomposition")
    d = m["pipeline_decomposition"]
    p(f"      routing_loss                         = {d['routing_loss']:.1%}")
    p(f"      navigation_loss | routing 正确        = {d['navigation_loss_given_correct_routing']:.1%}")
    p(f"      e2e_accuracy                         = {d['e2e_accuracy']:.1%}")
    p("=" * 64)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("results", help="trace JSON (富 trace 或 legacy agent_nav_*.json)")
    ap.add_argument("--questions", help="可选: data/test.json, 给 legacy 补 question/answer_type")
    ap.add_argument("--annotations", help="可选: {quid: category} 人工覆盖失败归类")
    ap.add_argument("--out", help="把指标 dict 写到此 JSON")
    args = ap.parse_args()

    raw = json.load(open(args.results, encoding="utf-8"))
    qmeta = {}
    if args.questions:
        for it in json.load(open(args.questions, encoding="utf-8")):
            qmeta[it["quid"]] = it
    traces = []
    for rec in raw:
        meta = qmeta.get(rec.get("quid"), {})
        traces.append(exp_trace.normalize_record(
            rec, question=meta.get("question"),
            answer_type=meta.get("answer_type"), time_level=meta.get("time_level")))

    anno = json.load(open(args.annotations, encoding="utf-8")) if args.annotations else None
    metrics = evaluate(traces, annotations=anno)
    print_report(metrics)
    if args.out:
        json.dump(metrics, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print(f"指标 -> {args.out}")


if __name__ == "__main__":
    main()
