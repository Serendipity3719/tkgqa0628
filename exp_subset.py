# -*- coding: utf-8 -*-
"""
exp_subset.py — 测量协议: 定向子集 eval + 配对显著性检验
===================================================================
解决 S2b 暴露的问题: n=100 单次整体对比被 LLM 运行间噪声(~±3-4pt)淹没,
无法验证 <5pt 的定向改动。

两个工具:
  1. 单文件: 按 qtype / answer_type / 问句关键词 切**定向子集**, 报 robust 准确率 + Wilson 95%CI。
  2. 双文件(同题配对): **McNemar 精确检验** —— 只看"翻转的题"(b=改对, c=改错),
     去掉题间方差, 这是检测定向改动是否真实有效的正确统计量。

用法:
    python exp_subset.py traces_blind3_100.json                      # 单文件子集分解
    python exp_subset.py traces_blind2_100.json traces_blind3_100.json --subset visit   # 配对检验
"""
import argparse, json, sys, re, math
import exp_eval

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PIVOT_QTYPES = {"after_first", "before_last", "before_after"}

# 关键词子集 (问句正则) —— 改动只在它影响的子集上验证, 最灵敏
KEYWORD_SUBSETS = {
    "visit":      r"visit|hosted|received .*visit",
    "appeal":     r"appeal|request|demand",
    "negotiate":  r"negotiat|meet|talk",
    "cooperate":  r"cooperat|collaborat",
    "denounce":   r"denounce|criticiz|condemn|accuse",
    "sign":       r"sign|agreement",
    "optimistic": r"optimistic|praise|endorse",
    "threaten":   r"threaten|attack|force",
}


def subsets_of(trace):
    """该题属于哪些子集 (可多归属)。"""
    m = trace["meta"]; q = (trace.get("question") or "").lower()
    tags = ["ALL", f"qtype:{m['gold_qtype']}", f"ans:{m.get('answer_type')}"]
    if m["gold_qtype"] in PIVOT_QTYPES:
        tags.append("has_pivot")
    if len(trace["answer"].get("gold", [])) > 1:
        tags.append("multi_answer")
    for name, rgx in KEYWORD_SUBSETS.items():
        if re.search(rgx, q):
            tags.append(f"kw:{name}")
    return tags


def wilson(k, n, z=1.96):
    """Wilson 95% 置信区间 (比正态更稳, 适合小 n)。返回 (lo, hi)。"""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z*z/n
    c = (p + z*z/(2*n)) / d
    h = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / d
    return (max(0, c-h), min(1, c+h))


def mcnemar_exact(b, c):
    """McNemar 精确双侧检验。b=A错B对, c=A对B错。返回 p 值。"""
    n = b + c
    if n == 0:
        return 1.0
    lo = min(b, c)
    p = 2 * sum(math.comb(n, k) for k in range(lo + 1)) * (0.5 ** n)
    return min(1.0, p)


def load(f):
    T = json.load(open(f, encoding="utf-8"))
    for t in T:
        t["_ok"] = exp_eval.recheck_correct(t)
    return {t["quid"]: t for t in T}


def single_report(f):
    T = load(f)
    bucket = {}   # tag -> [k, n]
    for t in T.values():
        for tag in subsets_of(t):
            b = bucket.setdefault(tag, [0, 0])
            b[0] += int(t["_ok"]); b[1] += 1
    print("=" * 70)
    print(f"定向子集 robust 准确率 + Wilson 95%CI   ({f}, n={len(T)})")
    print("=" * 70)
    for tag in sorted(bucket, key=lambda x: (x != "ALL", x)):
        k, n = bucket[tag]
        if n < 3 and tag != "ALL":
            continue
        lo, hi = wilson(k, n)
        print(f"  {tag:16s} {k:3d}/{n:<3d} = {k/n:5.0%}  [{lo:.0%},{hi:.0%}]  (±{(hi-lo)/2*100:.0f}pt)")


def paired_report(fa, fb, subset_filter=None):
    A, B = load(fa), load(fb)
    common = sorted(set(A) & set(B))
    print("=" * 70)
    print(f"配对 McNemar 检验  A={fa}  B={fb}  共同题 {len(common)}")
    if subset_filter:
        print(f"子集过滤: {subset_filter}")
    print("=" * 70)
    # 按子集分别做配对检验
    tags = ["ALL"] + [t for t in (
        [f"kw:{subset_filter}"] if subset_filter else
        sorted({tag for q in common for tag in subsets_of(A[q])}))]
    seen = set()
    for tag in tags:
        if tag in seen:
            continue
        seen.add(tag)
        qs = [q for q in common if tag == "ALL" or tag in subsets_of(A[q])]
        if len(qs) < 3:
            continue
        a_ok = sum(A[q]["_ok"] for q in qs)
        b_ok = sum(B[q]["_ok"] for q in qs)
        b = sum(1 for q in qs if not A[q]["_ok"] and B[q]["_ok"])   # 改对
        c = sum(1 for q in qs if A[q]["_ok"] and not B[q]["_ok"])   # 改错
        p = mcnemar_exact(b, c)
        sig = "  ** 显著" if p < 0.05 else ("  * 趋势" if p < 0.15 else "")
        print(f"  {tag:16s} n={len(qs):3d}  A={a_ok/len(qs):4.0%} B={b_ok/len(qs):4.0%}  "
              f"改对{b} 改错{c} 净{b-c:+d}  p={p:.3f}{sig}")
    print("-" * 70)
    print("  注: 改对/改错 = 配对翻转; 净>0 且 p<0.05 才算定向改动真实有效(去除了题间方差)。")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file_a")
    ap.add_argument("file_b", nargs="?", help="给第二个文件则做同题配对 McNemar 检验")
    ap.add_argument("--subset", help="只看某关键词子集 (visit/appeal/...)")
    args = ap.parse_args()
    if args.file_b:
        paired_report(args.file_a, args.file_b, args.subset)
    else:
        single_report(args.file_a)


if __name__ == "__main__":
    main()
