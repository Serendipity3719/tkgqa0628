# -*- coding: utf-8 -*-
"""
exp_runner.py — 出富 trace 的导航实验 runner (Task 1 的生产端)
===================================================================
复用 agent_nav.py 的底层管线 (LLM 客户端 / 只读 bash 工具 / 评分), 不重复造轮子;
只把 agent 循环重写成**记录富 trace** 的版本, 并新增 routing_mode ablation 旋钮。

routing_mode:
  oracle —— 把 qtype 喂给 Agent (现状; 路由是查表, 测的是路由上界)
  blind  —— 不给 qtype, Agent 仅凭问句 + 路由清单自己选 skill (测真实 Router 能力)

产出: 一个 trace JSON 列表 (exp_trace schema), 可直接喂 exp_eval.py。
用法:
    python exp_runner.py --n 100 --workers 6 --routing-mode blind --out traces_blind_100.json
"""
import argparse, json, os, re, time, threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import agent_nav as AN          # 复用: run_bash / _chat / _BLOCK / SYSTEM / is_correct ...
import exp_trace
import exp_eval
import exp_parse                # S2a: 解析前端


def build_user(question, qtype, answer_type, time_level, reveal):
    """reveal = 要喂给 Agent 的 gold facet 集合 (S1 facet-blind ablation)。
    全给 = oracle(旧行为); 空 = 全盲, Agent 须自行从问句推断 qtype/答案类型/粒度。"""
    lines = [f"问题: {question}"]
    if "qtype" in reveal:
        lines.append(f"qtype: {qtype}")
    if "answer_type" in reveal:
        lines.append(f"answer_type: {answer_type}")
    if "time_level" in reveal:
        lines.append(f"time_level: {time_level}")
    lines.append("请按工作流导航作答 (先选并装载合适的 skill, 再取证)。")
    return "\n".join(lines)


def split_thought(reply, block_match):
    """reply 去掉 bash 代码块后剩下的文字 = Agent 的 thought (含可能的 STATE 行)。"""
    if not block_match:
        return reply.strip()
    return (reply[:block_match.start()] + reply[block_match.end():]).strip()


# P3: 自反思关口 —— 在 Agent 第一次给 FINAL 时**有条件**注入一次聚焦自检。
# 详见 skills/_shared/REFLECT.md。
#
# ⚠️ 关键教训:
#   1) 通用版"每个 FINAL 都注入五项清单" = 净负 (ALL 82%→73%, p=0.031 显著)。
#   2) 空结果探针"给'无相关事实'前再核一次" = 净负 (2026-06-28 McNemar: 改对9/改错14/净-5)。
#      Agent 二次尝试失败后倾向于彻底放弃而非修正, 产生大量"正确答案→无相关事实"的回归。
#   3) 旧 _PLURAL_Q 用 countr 会把 "which country" 单答案题误判成复数题, 造成反射误触发。
#   回溯预算已在 NAVIGATION.md 中处理空结果, 不需要反射层再介入。
# 故 targeted reflection 现**仅保留更保守的不完整信号**。

# 复数问句标志 (只看问句, 无 gold, 盲态无泄漏)。只匹配明确复数形式;
# "which country/state/party/organization..." 这类单数问句不触发, 避免 REPORT_NEXT 记录的误触发。
_PLURAL_Q = re.compile(
    r"which\s+(?:countries|nations|states|parties|groups|organizations|leaders|people|sides)\b"
    r"|\bwho are\b|哪些|list (?:all|the)|all .*\bwho\b", re.I)


def _is_error_ans(ans):
    """API 错误/空答案/无答案不触发反思 (无意义或回溯已处理)。"""
    return ("[API_ERROR" in ans) or ("[无答案]" in ans) or (not ans.strip())


def _loaded_multianswer_skill(raw_steps):
    """Agent 自己是否路由到了多答案 skill (before_after/equal_multi)。
    用 agent 自身的路由选择当信号 —— 不是 gold qtype, 盲态无泄漏。"""
    for s in raw_steps:
        if re.search(r"skills[\\/](before_after|equal_multi)[\\/]", s.get("cmd", "")):
            return True
    return False


def _reflect_probe(question, cand, raw_steps):
    """targeted P3: 仅在检测到答案不完整时注入一条自检; 否则 None。
    空结果/无相关事实 由 NAVIGATION.md 回溯预算处理, 不在此介入
    (实测空结果探针导致 net -5 回归, 见 REFLECT.md 更新)。"""
    if _is_error_ans(cand):
        return None
    # 不再对"知识库中无相关事实"做反射 —— 回溯预算已覆盖, 反射层介入有害
    if "知识库中无相关事实" in cand:
        return None
    # 不完整信号: (agent 自己路由到多答案 skill 或问句明确复数) 却只给 1 个答案
    n_ans = len([p for p in re.split(r"\s*;\s*|\s*、\s*", cand) if p.strip()])
    if n_ans == 1 and (_loaded_multianswer_skill(raw_steps) or _PLURAL_Q.search(question or "")):
        return ("⚠️ 这看起来要多个答案却只给了一个, 可能漏了同侧其他对方。请在正确方向($2)上"
                "重跑过滤并 `sort -u` 看有几行; 确实只有一个就原样重发 `FINAL:`, 不要编造补充。")
    return None


def solve_traced(item, reveal, feed=None, predicted=None, max_cmds=11, reflect=False):
    """一题: 跑 agent 循环, 收集 [{cmd,obs,thought}] 原始步骤。
    reveal=喂入的 facet 集合; feed=要显示的 facet 值(默认 gold; parse 模式传预测值);
    predicted=parse 前端预测的 facet(记入 trace, 非 None 即 parse 模式);
    reflect=P3 自反思关口: 第一次 FINAL 时注入一次自检, 给 +3 命令预算核实/修正。"""
    feed = feed or {"qtype": item["qtype"], "answer_type": item.get("answer_type"),
                    "time_level": item.get("time_level", "day")}
    user = build_user(item["question"], feed["qtype"], feed["answer_type"],
                      feed["time_level"], reveal)
    # ============================
    # NG-LAYER INJECTION (Route B)
    # ============================
    import os
    from navigation_graph import build_graph
    from ng_prompt_builder import build_ng_prompt

    NG_ENABLE = os.getenv("NG_ENABLE", "0") == "1"

    if NG_ENABLE and args.reveal == "none":
        g = build_graph(item["question"])
        ng_ctx = build_ng_prompt(item["question"], g)

        # 关键：只增强 user，不动 system / messages 结构
        user = ng_ctx + "\n\n" + user
        
    messages = [{"role": "system", "content": AN.SYSTEM},
                {"role": "user", "content": user}]
    raw_steps, cmds, final = [], 0, "[无答案]"
    reflected = False
    hard_cap = max_cmds + (3 if reflect else 0)   # 反思后允许少量额外命令核实

    for _turn in range(hard_cap + 5):
        reply = AN._chat(messages)
        messages.append({"role": "assistant", "content": reply})
        mfin = re.search(r"FINAL:\s*(.+)", reply, re.S)
        mblk = AN._BLOCK.search(reply)
        blk_is_final = bool(mblk and mblk.group(1).strip().upper().startswith("FINAL:"))

        # 命令优先 (块是命令, 且在 FINAL 之前)
        if mblk and not blk_is_final and (not mfin or mblk.start() < mfin.start()):
            cmd = mblk.group(1).strip()
            cmds += 1
            obs = AN.run_bash(cmd)
            raw_steps.append({"cmd": cmd, "obs": obs[:600],
                              "thought": split_thought(reply, mblk)[:500]})
            if cmds > hard_cap:
                messages.append({"role": "user", "content": "命令数已达上限, 请基于已有证据给出 FINAL。"})
            else:
                messages.append({"role": "user", "content": f"命令输出:\n{obs}"})
            continue

        # 取候选 FINAL (块内 FINAL 或文本 FINAL)
        cand = None
        if blk_is_final:
            cand = mblk.group(1).strip()[6:].strip()
        elif mfin:
            cand = mfin.group(1).strip()
        if cand is None:
            messages.append({"role": "user", "content": "请输出一个 ```bash 命令块, 或给出 FINAL:。"})
            continue

        # P3 反思关口: 第一次给真实 FINAL 且**命中风险信号**时, 注入一次聚焦自检
        if reflect and not reflected and cmds <= max_cmds:
            probe = _reflect_probe(item["question"], cand, raw_steps)
            if probe:
                reflected = True
                messages.append({"role": "user", "content": probe})
                continue

        final = cand
        break

    ok = AN.is_correct(final, item["answers"], item.get("answer_type"))
    tr = exp_trace.build_trace(
        quid=item["quid"], question=item["question"], gold_qtype=item["qtype"],
        answer_type=item.get("answer_type"), time_level=item.get("time_level", "day"),
        raw_steps=raw_steps, final=final, gold=item["answers"], correct=ok,
        revealed_facets=reveal, predicted_facets=predicted, model="deepseek-chat")
    tr.setdefault("meta", {})["reflect"] = bool(reflect)
    tr["meta"]["reflected"] = reflected
    return tr


def solve_parse(item, max_cmds=11):
    """parse 模式: 先自推 facet, 再把**预测值**当 facet 喂给 serve 循环 (不碰任何 gold)。"""
    pred = exp_parse.parse_question(item["question"])
    return solve_traced(item, reveal=list(exp_trace.ALL_FACETS), feed=pred,
                        predicted=pred, max_cmds=max_cmds)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--workers", type=int, default=6)
    # 喂给 Agent 的 gold facet 子集; 逗号分隔。'all'=oracle(旧); 'none'=全盲。
    # 也可单独保留, 如 --reveal answer_type,time_level 只盲 qtype。
    ap.add_argument("--reveal", default="all",
                    help="qtype,answer_type,time_level 的子集 | all | none")
    ap.add_argument("--parse", action="store_true",
                    help="S2a: 用 parse 前端自推 facet 代替 gold (隐含 reveal=all 但喂预测值)")
    ap.add_argument("--reflect", action="store_true",
                    help="P3: 开启自反思关口 (第一次 FINAL 时注入一次通用自检, +3 命令预算)")
    ap.add_argument("--data", default=os.path.join("data", "test.json"))
    ap.add_argument("--out", default="traces.json")
    ap.add_argument("--eval", action="store_true", help="跑完直接打印 exp_eval 报告")
    args = ap.parse_args()

    if args.reveal == "all":
        reveal = list(exp_trace.ALL_FACETS)
    elif args.reveal == "none":
        reveal = []
    else:
        reveal = [f.strip() for f in args.reveal.split(",") if f.strip()]
        bad = set(reveal) - set(exp_trace.ALL_FACETS)
        if bad:
            ap.error(f"未知 facet: {bad}; 允许 {exp_trace.ALL_FACETS}")

    data = json.load(open(args.data, encoding="utf-8"))[:args.n]
    mode = "parse" if args.parse else ("oracle" if "qtype" in reveal else "blind")
    refl = " +reflect" if args.reflect else ""
    print(f"导航实验 mode={mode}{refl} reveal={reveal or 'none'}: {len(data)} 题, {args.workers} 并发 ...")
    t0, traces, done = time.time(), [], 0
    lock = threading.Lock()
    worker = (lambda it: solve_parse(it)) if args.parse else (lambda it: solve_traced(it, reveal, reflect=args.reflect))
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = [ex.submit(worker, it) for it in data]
        for fut in as_completed(futs):
            t = fut.result()
            with lock:
                traces.append(t); done += 1
                if done % 10 == 0:
                    acc = sum(x["answer"]["correct"] for x in traces) / len(traces)
                    print(f"  {done}/{len(data)}  acc={acc:.1%}  ({time.time()-t0:.0f}s)")

    traces.sort(key=lambda t: t["quid"])
    json.dump(traces, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"富 trace -> {args.out}  ({time.time()-t0:.0f}s)")
    if args.eval:
        exp_eval.print_report(exp_eval.evaluate(traces))


if __name__ == "__main__":
    main()
