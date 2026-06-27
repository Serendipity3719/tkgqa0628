# -*- coding: utf-8 -*-
"""
exp_eval.py — TKG2Skill 实验评估模块 (S1 校准版)
===================================================================
读 trace JSON (富 trace 或 legacy agent_nav_*.json), 产出范式有效性分析:

  1. Skill Routing Accuracy      —— Router 选对 skill 的比例 (+ 混淆矩阵)
  2. End-to-End QA Accuracy      —— 整链命中率 (+ robust 重判, 修打分假阴性)
  3. Navigation Efficiency       —— avg steps / tool calls / evidence / backtracks
  4. Failure Taxonomy            —— 见 FAILURE_CATS (S1② 人工校准后的真实分类)
  5. Pipeline Loss Decomposition —— 损耗拆给 routing 段 vs navigation 段
  6. Classifier Calibration      —— 启发式分类器 vs 人工标注的一致率

S1② 关键修正 (经 agent_nav_100 全部 15 失败逐条人工读轨迹):
  - 原 'temporal_reasoning_error' 桶是**伪命中** (人工核验 0/15 真为时序推理错)。
    本版分类器**不再默认归 temporal**: 只在高置信信号下给标签, 其余 → needs_review。
  - 新增可观测、高置信的判定: scoring_artifact (打分假阴性)、answer_incompleteness
    (PRED ⊊ GOLD)、relation_direction_error、entity_resolution_error。
  - **人工标注优先** (--annotations): 启发式仅作无标注时的保守回退。

用法:
    python exp_eval.py agent_nav_100.json --questions data/test.json \
        --annotations failure_annotations.json
"""
import argparse, json, collections, sys, re
import exp_trace

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# S1② 校准后的失败分类 (替换原 5 类; 含本不是"模型失败"的 eval/gold 问题)
FAILURE_CATS = [
    "scoring_artifact",          # 预测其实正确, eval 假阴性 (格式/归一化) —— eval bug, 非模型错
    "gold_or_question_issue",    # gold 与题面冲突 (问 country 但 gold 含人/组织) —— 数据问题, 非模型错
    "routing_error",             # 装错 skill (盲态尤其: before_after 误装 after_first 等)
    "answer_incompleteness",     # 多答案题只回了 gold 的真子集 —— 模型召回不全
    "entity_resolution_error",   # 锚/枢轴实体解析错或路径错
    "relation_direction_error",  # 关系码错 或 方向(>/<)错 (含 Host vs Make)
    "temporal_position_error",   # 时间位置/枢轴日期选择错 (其余皆对时才记此)
    "answer_selection_error",    # 取到正确证据却输出了别的最终答案
    "execution_error",           # 工具/命令崩溃未恢复
    "needs_review",              # 轨迹不足以高置信判定 —— 诚实留白, 不臆测
]
# 哪些类**不算模型能力失败** (用于诚实地分离 eval/数据噪声)
NON_MODEL_CATS = {"scoring_artifact", "gold_or_question_issue"}


# ---- robust 归一化 + 重判 (修打分假阴性, 如尾部 markdown **) ----------------
def robust_norm(x):
    s = str(x).replace("_", " ").lower()
    s = re.sub(r"[*`#]", "", s)            # 去 markdown
    s = re.sub(r"\s+", " ", s).strip()
    s = s.strip(" .,:;!?\"'")              # 去首尾标点
    return s


def _final_set(final):
    parts = [p for p in re.split(r"\s*;\s*|\s*、\s*", str(final).strip()) if p.strip()]
    return set(robust_norm(p) for p in parts if robust_norm(p))


def recheck_correct(trace):
    """用 robust 归一化重判对错 (entity=集合相等, time=互为前缀)。返回 bool。"""
    ans = trace["answer"]
    final = ans.get("final") or ""
    if any(m in final for m in ("知识库中无相关事实", "[无答案]", "[API_ERROR", "[错误]")):
        return False
    pred = _final_set(final)
    gold = set(robust_norm(g) for g in ans.get("gold", []))
    if not pred or not gold:
        return False
    if trace["meta"].get("answer_type") == "time":
        return any(a == b or a.startswith(b) or b.startswith(a) for a in pred for b in gold)
    return pred == gold


# ---- 失败归类 (保守版: 只给高置信标签, 否则 needs_review) -------------------
def classify_failure(trace):
    """返回 (category, evidence)。仅对答错的题调用。**不再默认 temporal。**"""
    nav, rt, ans = trace["navigation"], trace["routing"], trace["answer"]
    steps = nav["steps"]
    final = ans.get("final") or ""
    pred = _final_set(final)
    gold = set(robust_norm(g) for g in ans.get("gold", []))

    # 0) 打分假阴性: robust 重判其实正确
    if recheck_correct(trace):
        return "scoring_artifact", "robust-norm 下 PRED==GOLD; 原 eval 假阴性"
    # 1) 执行层崩溃 / 根本没答
    if any(m in final for m in ("[API_ERROR", "[无答案]", "[错误]")) or not final.strip():
        return "execution_error", "run broke / no FINAL"
    # 2) 路由错 (装错 skill) —— 仅当确实观测到 skill 装载且不符
    if rt["routing_observed"] and not rt["routing_correct"]:
        return "routing_error", f"loaded {rt['selected_skill']} != gold {rt['gold_skill']}"
    # 3) 实体/枢轴解析: pivot-not-found / 路径错 / 锚未绑定
    pivot_nf = any("[pivot-not-found]" in (s["observation"] or "") for s in steps)
    path_err = any("No such file" in (s["observation"] or "") for s in steps)
    if pivot_nf or path_err or not nav["reconstructed_state"].get("D"):
        return "entity_resolution_error", "pivot/anchor/path 未解析 (high-conf)"
    # 4) 多答案题: PRED 是 GOLD 的非空真子集 → 召回不全 (可观测, 高置信)
    if pred and gold and pred < gold:
        return "answer_incompleteness", f"PRED({len(pred)}) ⊊ GOLD({len(gold)})"
    # 5) 其余答错: 启发式无法高置信区分 relation/direction/temporal/选择 → 诚实留白
    return "needs_review", "evidence 存在但根因需读轨迹/人工标注 (勿臆测为 temporal)"


def _mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else 0.0


def _resolve_cat(trace, annotations):
    """优先人工标注, 否则保守启发式。返回 (cause, source, evidence)。"""
    quid = str(trace["quid"])
    if quid in annotations:
        a = annotations[quid]
        cause = a["cause"] if isinstance(a, dict) else a
        return cause, "manual", (a.get("note", "") if isinstance(a, dict) else "")
    c, ev = classify_failure(trace)
    return c, "heuristic", ev


def evaluate(traces, annotations=None):
    annotations = {k: v for k, v in (annotations or {}).items() if not k.startswith("_")}

    # --- robust 重判, 统计打分假阴性 ---
    false_neg = 0
    for t in traces:
        t["_recheck_correct"] = recheck_correct(t)
        if (not t["answer"]["correct"]) and t["_recheck_correct"]:
            false_neg += 1

    # --- 失败归类 (人工优先) ---
    wrong_ts = [t for t in traces if not t["answer"]["correct"]]
    for t in wrong_ts:
        cause, src, ev = _resolve_cat(t, annotations)
        t["failure"] = {"is_failure": True, "category": cause, "source": src, "evidence": ev}

    # --- 1. Routing Accuracy ---
    routed = [t for t in traces if t["routing"]["routing_observed"]]
    routing_acc = _mean(t["routing"]["routing_correct"] for t in routed)
    confusion = collections.Counter(
        (t["routing"]["gold_skill"], t["routing"]["selected_skill"]) for t in routed)

    # --- 2. E2E Accuracy (原始 + robust 重判) ---
    e2e_raw = _mean(t["answer"]["correct"] for t in traces)
    e2e_robust = _mean(t["_recheck_correct"] for t in traces)
    per_qtype = {}
    by_qt = collections.defaultdict(list)
    for t in traces:
        by_qt[t["meta"]["gold_qtype"]].append(t)
    for qt, ts in sorted(by_qt.items()):
        per_qtype[qt] = {"n": len(ts), "acc": _mean(x["answer"]["correct"] for x in ts),
                         "acc_robust": _mean(x["_recheck_correct"] for x in ts)}

    # --- 3. Navigation Efficiency ---
    def eff(ts):
        return {"avg_steps": _mean(x["navigation"]["num_steps"] for x in ts),
                "avg_evidence": _mean(x["navigation"]["num_evidence_calls"] for x in ts),
                "avg_backtracks": _mean(x["navigation"]["num_backtracks"] for x in ts)}
    efficiency = {"all": eff(traces),
                  "correct": eff([t for t in traces if t["_recheck_correct"]]),
                  "incorrect": eff([t for t in traces if not t["_recheck_correct"]])}

    # --- 4. Failure Taxonomy (基于 robust 重判后仍错的题) ---
    true_wrong = [t for t in traces if not t["_recheck_correct"]]
    for t in true_wrong:
        if "failure" not in t:
            cause, src, ev = _resolve_cat(t, annotations)
            t["failure"] = {"is_failure": True, "category": cause, "source": src, "evidence": ev}
    fail_counts = collections.Counter(t["failure"]["category"] for t in true_wrong)
    taxonomy = {c: fail_counts.get(c, 0) for c in FAILURE_CATS if fail_counts.get(c, 0)}
    model_fail = sum(n for c, n in fail_counts.items() if c not in NON_MODEL_CATS)
    nonmodel_fail = sum(n for c, n in fail_counts.items() if c in NON_MODEL_CATS)

    # --- 5. Pipeline Loss Decomposition (用 robust 准确率) ---
    routed_ok = [t for t in routed if t["routing"]["routing_correct"]]
    nav_acc_given_routing = _mean(t["_recheck_correct"] for t in routed_ok)
    decomposition = {"routing_loss": 1.0 - routing_acc,
                     "navigation_loss_given_correct_routing": 1.0 - nav_acc_given_routing,
                     "e2e_accuracy_robust": e2e_robust}

    # --- 6b. Parse 前端准确率 (S2a: predicted_facets vs gold) ---
    parsed = [t for t in traces if t["meta"].get("predicted_facets")]
    parse_acc = None
    if parsed:
        def pc(t, facet, gold_key):
            return t["meta"]["predicted_facets"].get(facet) == t["meta"].get(gold_key)
        parse_acc = {
            "n": len(parsed),
            "qtype": _mean(pc(t, "qtype", "gold_qtype") for t in parsed),
            "skill_route": _mean(
                exp_trace.GOLD_SKILL.get(t["meta"]["predicted_facets"].get("qtype"))
                == exp_trace.GOLD_SKILL.get(t["meta"]["gold_qtype"]) for t in parsed),
            "answer_type": _mean(pc(t, "answer_type", "answer_type") for t in parsed),
            "time_level": _mean(pc(t, "time_level", "time_level") for t in parsed),
            "all_three": _mean(
                pc(t, "qtype", "gold_qtype") and pc(t, "answer_type", "answer_type")
                and pc(t, "time_level", "time_level") for t in parsed),
        }

    # --- 6. Classifier Calibration (启发式 vs 人工) ---
    calib = None
    labeled = [t for t in true_wrong if str(t["quid"]) in annotations]
    if labeled:
        agree = 0
        for t in labeled:
            h, _ = classify_failure(t)
            m = annotations[str(t["quid"])]
            mc = m["cause"] if isinstance(m, dict) else m
            agree += int(h == mc)
        calib = {"n_labeled": len(labeled), "heuristic_vs_manual_agreement": agree / len(labeled)}

    return {
        "n": len(traces),
        "routing_mode": traces[0]["meta"].get("routing_mode") if traces else None,
        "revealed_facets": traces[0]["meta"].get("revealed_facets") if traces else None,
        "routing_accuracy": routing_acc,
        "routing_confusion": {f"{g}->{s}": c for (g, s), c in sorted(confusion.items())},
        "e2e_accuracy_raw": e2e_raw,
        "e2e_accuracy_robust": e2e_robust,
        "scoring_false_negatives": false_neg,
        "per_qtype": per_qtype,
        "navigation_efficiency": efficiency,
        "failure_taxonomy": taxonomy,
        "failure_attribution": {"model_failures": model_fail, "non_model_eval_or_gold": nonmodel_fail},
        "pipeline_decomposition": decomposition,
        "parse_accuracy": parse_acc,
        "classifier_calibration": calib,
    }


def print_report(m):
    p = print
    p("=" * 66)
    p(f"TKG2Skill 评估  n={m['n']}  routing_mode={m['routing_mode']}  reveal={m['revealed_facets']}")
    p("=" * 66)
    if m.get("parse_accuracy"):
        pa = m["parse_accuracy"]
        p(f"[0] Parse 前端 (n={pa['n']}): skill路由 {pa['skill_route']:.0%} | qtype {pa['qtype']:.0%} | "
          f"answer_type {pa['answer_type']:.0%} | time_level {pa['time_level']:.0%} | 三者全对 {pa['all_three']:.0%}")
    p(f"[1] Skill Routing Accuracy : {m['routing_accuracy']:.1%}")
    if m["routing_mode"] == "oracle":
        p("    ⚠ oracle: qtype 已喂入, 该数字是路由上界, 非真实路由能力")
    p(f"[2] End-to-End Accuracy    : raw {m['e2e_accuracy_raw']:.1%}  ->  robust {m['e2e_accuracy_robust']:.1%}"
      f"  (修复 {m['scoring_false_negatives']} 个打分假阴性)")
    for qt, d in m["per_qtype"].items():
        p(f"      {qt:14s} n={d['n']:<4d} acc {d['acc']:.0%} -> robust {d['acc_robust']:.0%}")
    p(f"[3] Navigation Efficiency  (steps / evidence / backtrack)")
    for k in ("all", "correct", "incorrect"):
        e = m["navigation_efficiency"][k]
        p(f"      {k:10s} {e['avg_steps']:.1f} / {e['avg_evidence']:.1f} / {e['avg_backtracks']:.2f}")
    fa = m["failure_attribution"]
    p(f"[4] Failure Taxonomy  (robust 后真失败; 模型错 {fa['model_failures']} / eval-gold 噪声 {fa['non_model_eval_or_gold']})")
    for c, n in sorted(m["failure_taxonomy"].items(), key=lambda kv: -kv[1]):
        tag = "  (非模型)" if c in NON_MODEL_CATS else ""
        p(f"      {c:26s} {n}{tag}")
    d = m["pipeline_decomposition"]
    p(f"[5] Pipeline Loss:  routing_loss {d['routing_loss']:.1%}  |  "
      f"navigation_loss|routing对 {d['navigation_loss_given_correct_routing']:.1%}")
    if m["classifier_calibration"]:
        c = m["classifier_calibration"]
        p(f"[6] Classifier Calibration: 启发式 vs 人工 一致率 {c['heuristic_vs_manual_agreement']:.0%} "
          f"(n={c['n_labeled']})")
    p("=" * 66)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("results")
    ap.add_argument("--questions", help="data/test.json, 给 legacy 补 question/answer_type")
    ap.add_argument("--annotations", help="failure_annotations.json (人工标注优先)")
    ap.add_argument("--out")
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
