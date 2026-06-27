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


def solve_traced(item, reveal, feed=None, predicted=None, max_cmds=11):
    """一题: 跑 agent 循环, 收集 [{cmd,obs,thought}] 原始步骤。
    reveal=喂入的 facet 集合; feed=要显示的 facet 值(默认 gold; parse 模式传预测值);
    predicted=parse 前端预测的 facet(记入 trace, 非 None 即 parse 模式)。"""
    feed = feed or {"qtype": item["qtype"], "answer_type": item.get("answer_type"),
                    "time_level": item.get("time_level", "day")}
    user = build_user(item["question"], feed["qtype"], feed["answer_type"],
                      feed["time_level"], reveal)
    messages = [{"role": "system", "content": AN.SYSTEM},
                {"role": "user", "content": user}]
    raw_steps, cmds, final = [], 0, "[无答案]"

    for _turn in range(max_cmds + 4):
        reply = AN._chat(messages)
        messages.append({"role": "assistant", "content": reply})
        mfin = re.search(r"FINAL:\s*(.+)", reply, re.S)
        mblk = AN._BLOCK.search(reply)

        # FINAL 被误包进 ```bash 块
        if mblk and mblk.group(1).strip().upper().startswith("FINAL:"):
            final = mblk.group(1).strip()[6:].strip(); break
        if mblk and (not mfin or mblk.start() < mfin.start()):
            cmd = mblk.group(1).strip()
            cmds += 1
            obs = AN.run_bash(cmd)
            raw_steps.append({"cmd": cmd, "obs": obs[:600],
                              "thought": split_thought(reply, mblk)[:500]})
            if cmds > max_cmds:
                messages.append({"role": "user", "content": "命令数已达上限, 请基于已有证据给出 FINAL。"})
            else:
                messages.append({"role": "user", "content": f"命令输出:\n{obs}"})
            continue
        if mfin:
            final = mfin.group(1).strip(); break
        messages.append({"role": "user", "content": "请输出一个 ```bash 命令块, 或给出 FINAL:。"})

    ok = AN.is_correct(final, item["answers"], item.get("answer_type"))
    return exp_trace.build_trace(
        quid=item["quid"], question=item["question"], gold_qtype=item["qtype"],
        answer_type=item.get("answer_type"), time_level=item.get("time_level", "day"),
        raw_steps=raw_steps, final=final, gold=item["answers"], correct=ok,
        revealed_facets=reveal, predicted_facets=predicted, model="deepseek-chat")


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
    print(f"导航实验 mode={mode} reveal={reveal or 'none'}: {len(data)} 题, {args.workers} 并发 ...")
    t0, traces, done = time.time(), [], 0
    lock = threading.Lock()
    worker = (lambda it: solve_parse(it)) if args.parse else (lambda it: solve_traced(it, reveal))
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
