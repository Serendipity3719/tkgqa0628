# -*- coding: utf-8 -*-
"""
build.py — TKGQA 文件系统知识库构建器
===================================================================
读取四元组大表 (head \t relation \t tail \t date)，构建一个面向
Deep Agent 文件系统导航的结构化知识库。无 LLM 参与，纯 Python 确定性切分。

核心设计（详见随附方案）：
  * 双向冗余存储：每条四元组同时写入 head 实体与 tail 实体两个目录，
    带方向标记 '>'(本实体是 head) / '<'(本实体是 tail)。
  * 每个实体 = 一个目录，内含 data.txt（按日期升序），大实体附 INDEX.md。
  * _catalog.tsv 是唯一入口（规范名 -> 安全路径），Agent grep 取精确路径。
  * 不切年、不建全局时间索引（当前 6 类查询全是 实体+关系+时序）。
  * 日期 YYYY-MM-DD，字典序即时间序。

用法:
    python build.py                       # 默认 data/full.txt -> database/
    python build.py --input data/full.txt --out database --index-threshold 2000

幂等：每次运行会清空并重建 --out 目录。
"""

import argparse
import os
import shutil
import sys
import time
from collections import defaultdict, Counter

# Windows / 跨平台文件名非法字符
_ILLEGAL = '<>:"/\\|?*'
_ILLEGAL_MAP = {ord(c): '_' for c in _ILLEGAL}
# 控制字符
for _i in range(0, 32):
    _ILLEGAL_MAP[_i] = '_'
# Windows 保留设备名
_RESERVED = {
    'CON', 'PRN', 'AUX', 'NUL',
    *(f'COM{i}' for i in range(1, 10)),
    *(f'LPT{i}' for i in range(1, 10)),
}


def safe_name(name):
    """把实体规范名转成一个文件系统安全的目录名（不保证唯一，唯一性在调用处处理）。"""
    s = name.translate(_ILLEGAL_MAP)
    # Windows 不允许结尾的点或空格
    s = s.rstrip(' .')
    if not s:
        s = '_empty'
    if s.upper() in _RESERVED:
        s = s + '_'
    # 限制单段长度，避免极端长路径（实体名一般很短，保险起见）
    if len(s) > 150:
        s = s[:150]
    return s


def bucket_of(safe):
    """按安全名首字符分桶，仅为文件系统整洁。"""
    c = safe[0]
    if c.isalnum():
        return c.lower()
    return '_other'


def main():
    ap = argparse.ArgumentParser(description='Build TKGQA filesystem knowledge base.')
    ap.add_argument('--input', default=os.path.join('data', 'full.txt'),
                    help='输入四元组 TSV（head\\trelation\\ttail\\tdate，无表头，UTF-8）')
    ap.add_argument('--out', default='database', help='输出知识库目录')
    ap.add_argument('--index-threshold', type=int, default=2000,
                    help='实体记录数超过该阈值才生成 INDEX.md（默认 2000）')
    ap.add_argument('--top-n', type=int, default=15,
                    help='INDEX.md 中高频关系/邻居各取前 N（默认 15）')
    args = ap.parse_args()

    t_start = time.time()
    in_path = args.input
    out_dir = args.out

    if not os.path.isfile(in_path):
        print(f'[FATAL] 找不到输入文件: {in_path}', file=sys.stderr)
        print('  请确认大 TSV 放在 data/full.txt，或用 --input 指定路径。', file=sys.stderr)
        sys.exit(1)

    # ---- 1. 读取并双向归集 ----
    # records[entity] = list of (date, direction, relation, other)
    records = defaultdict(list)
    rel_freq = Counter()
    n_lines = 0
    n_bad = 0

    print(f'[1/5] 读取 {in_path} ...')
    with open(in_path, 'r', encoding='utf-8', newline='') as f:
        for line in f:
            line = line.rstrip('\n').rstrip('\r')
            if not line:
                continue
            parts = line.split('\t')
            if len(parts) != 4:
                n_bad += 1
                continue
            head, rel, tail, date = parts
            n_lines += 1
            rel_freq[rel] += 1
            # 本实体视角：head 看到 '>'(指向 tail)，tail 看到 '<'(被 head 指向)
            records[head].append((date, '>', rel, tail))
            records[tail].append((date, '<', rel, head))

    print(f'      四元组: {n_lines:,}  (跳过非法行: {n_bad})')
    print(f'      实体数: {len(records):,}   关系数: {len(rel_freq):,}')

    # ---- 2. 安全名映射 + 唯一化 ----
    print('[2/5] 生成安全名映射 ...')
    used = {}             # safe(lower) -> canonical（用于冲突检测，大小写不敏感避免 NTFS 冲突）
    name_to_path = {}     # canonical -> 相对路径 entities/<bucket>/<safe>
    # 排序保证幂等（确定性）
    for canonical in sorted(records.keys()):
        base = safe_name(canonical)
        bucket = bucket_of(base)
        candidate = base
        n = 1
        # 冲突：同一安全名（忽略大小写）落到不同规范名 -> 加数字后缀
        while (bucket, candidate.lower()) in used and used[(bucket, candidate.lower())] != canonical:
            candidate = f'{base}_{n}'
            n += 1
        used[(bucket, candidate.lower())] = canonical
        name_to_path[canonical] = os.path.join('entities', bucket, candidate).replace('\\', '/')

    # ---- 3. 清空并落盘 data.txt ----
    print(f'[3/5] 写入实体数据到 {out_dir}/ ...')
    if os.path.isdir(out_dir):
        shutil.rmtree(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(os.path.join(out_dir, 'entities'), exist_ok=True)

    catalog_rows = []           # (canonical, relpath, count, min_date, max_date)
    big_entities = []           # 触发 INDEX.md 的实体
    written = 0
    for canonical in sorted(records.keys()):
        rel_path = name_to_path[canonical]
        abs_dir = os.path.join(out_dir, *rel_path.split('/'))
        os.makedirs(abs_dir, exist_ok=True)
        rows = records[canonical]
        # 按 (日期, 方向, 关系, 对方) 升序 —— 日期字典序即时间序，后三键仅为确定性
        rows.sort()
        with open(os.path.join(abs_dir, 'data.txt'), 'w', encoding='utf-8', newline='\n') as wf:
            wf.writelines(f'{d}\t{dir_}\t{r}\t{o}\n' for (d, dir_, r, o) in rows)
        cnt = len(rows)
        catalog_rows.append((canonical, rel_path, cnt, rows[0][0], rows[-1][0]))
        if cnt > args.index_threshold:
            big_entities.append(canonical)
        written += 1
        if written % 2000 == 0:
            print(f'      ... {written:,}/{len(records):,} 实体已写入')

    # ---- 4. 写入 catalog / relations / README ----
    print('[4/5] 写入 _catalog.tsv / _relations.txt / _README_layout.txt ...')
    # _catalog.tsv : 规范名 \t 目录路径 \t 四元组数 \t 最早日期 \t 最晚日期
    with open(os.path.join(out_dir, '_catalog.tsv'), 'w', encoding='utf-8', newline='\n') as cf:
        cf.write('# canonical_name\tdir_path\tcount\tmin_date\tmax_date\n')
        for canonical, rel_path, cnt, dmin, dmax in sorted(catalog_rows):
            cf.write(f'{canonical}\t{rel_path}\t{cnt}\t{dmin}\t{dmax}\n')

    # _relations.txt : 关系编码 \t 频次 （按频次降序，便于 NL->关系映射时优先高频）
    with open(os.path.join(out_dir, '_relations.txt'), 'w', encoding='utf-8', newline='\n') as rf:
        rf.write('# relation_code\tfrequency\n')
        for rel, fr in rel_freq.most_common():
            rf.write(f'{rel}\t{fr}\n')

    # ---- 5. 大实体 INDEX.md ----
    print(f'[5/5] 为 {len(big_entities)} 个大实体(>{args.index_threshold} 条)生成 INDEX.md ...')
    for canonical in big_entities:
        rows = records[canonical]
        rel_path = name_to_path[canonical]
        abs_dir = os.path.join(out_dir, *rel_path.split('/'))
        per_year = Counter(d[:4] for (d, _, _, _) in rows)
        rel_cnt = Counter(r for (_, _, r, _) in rows)
        nbr_cnt = Counter(o for (_, _, _, o) in rows)
        dir_cnt = Counter(dir_ for (_, dir_, _, _) in rows)
        with open(os.path.join(abs_dir, 'INDEX.md'), 'w', encoding='utf-8', newline='\n') as mf:
            mf.write(f'# {canonical}\n\n')
            mf.write(f'- 总事件数: {len(rows)}\n')
            mf.write(f'- 时间跨度: {rows[0][0]} ~ {rows[-1][0]}\n')
            mf.write(f"- 方向分布: 作为 head(>) {dir_cnt.get('>', 0)} 条 | 作为 tail(<) {dir_cnt.get('<', 0)} 条\n\n")
            mf.write('## 逐年事件计数\n\n')
            for y in sorted(per_year):
                mf.write(f'- {y}: {per_year[y]}\n')
            mf.write(f'\n## 高频关系 (Top {args.top_n})\n\n')
            for r, c in rel_cnt.most_common(args.top_n):
                mf.write(f'- {r}\t{c}\n')
            mf.write(f'\n## 高频邻居 (Top {args.top_n})\n\n')
            for o, c in nbr_cnt.most_common(args.top_n):
                mf.write(f'- {o}\t{c}\n')

    # _README_layout.txt（给 Agent 看的格式说明）
    with open(os.path.join(out_dir, '_README_layout.txt'), 'w', encoding='utf-8', newline='\n') as rm:
        rm.write(README_LAYOUT.format(threshold=args.index_threshold))

    dt = time.time() - t_start
    print('\n=== 完成 ===')
    print(f'  输出目录   : {out_dir}/')
    print(f'  实体目录   : {len(records):,}')
    print(f'  关系编码   : {len(rel_freq):,}')
    print(f'  大实体索引 : {len(big_entities)} (阈值 >{args.index_threshold})')
    print(f'  耗时       : {dt:.1f}s')


README_LAYOUT = """TKGQA 文件系统知识库 —— 布局说明 (给 Agent)
=====================================================================

目录结构:
  database/
    _catalog.tsv          唯一入口：实体规范名 -> 安全目录路径
    _relations.txt        全部关系编码 + 频次（NL 短语 -> 关系编码映射用）
    _README_layout.txt    本文件
    entities/<桶>/<安全名>/
        data.txt          该实体全部相关四元组，已按日期升序
        INDEX.md          仅 >{threshold} 条的大实体生成：逐年计数/高频关系/高频邻居

_catalog.tsv 列:
    canonical_name \\t dir_path \\t count \\t min_date \\t max_date
  规范名与 data.txt 里的实体名用【下划线】连接（如 Jack_Straw）。
  Agent 切勿自己拼路径，务必 grep catalog 取 dir_path。

data.txt 行格式（以本实体为视角）:
    日期 \\t 方向 \\t 关系 \\t 对方
    2005-04-12 \\t < \\t Sign_agreement \\t Iran
  方向: '>' = 本实体是 head（本实体 -> 对方）
        '<' = 本实体是 tail（对方 -> 本实体）
  日期 YYYY-MM-DD，字典序即时间序：$1<t0 / $1>t0 / head -1 / tail -1 均成立。

重要约定:
  * 实体名与关系编码在库内一律用下划线。测试集标准答案用【空格】，
    抽出实体后输出前需把下划线还原为空格（Jack_Straw -> Jack Straw）。
  * 双向冗余：每条事实在 head 与 tail 两个目录各存一份，
    所以 tail 类问题（"谁访问了X"）只需读 X 的 data.txt，无需全库扫描。
  * 永远用 awk 过滤，绝不 cat 整个 data.txt 进上下文。
"""


if __name__ == '__main__':
    main()
