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
  * 大实体(>index-threshold 条)生成 INDEX.md(逐年地图)+by_year/<年>.txt(时序切片),支持渐进披露导航。
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


# =====================================================================
# 关系族投影 (P1): 把 N 个关系码确定性地聚成 <=30 个"关系族"
# ---------------------------------------------------------------------
# 动机: NAVIGATION.md 原来靠手写散文把 NL 谓词映射到关系码, 251 个关系只手映了
#       ~10 个, 是 relation/direction 绑定错(第一失败源)的根因, 且换数据集即废。
# 设计: 纯词法 (leading-verb / 关键词) 聚类, 一遍式确定性, 第一个命中的规则胜出;
#       embedding 仅作可选开关 (--rel-embedding), 用于把落入 'other' 的关系再归并。
# 产出: database/_relation_families.tsv  (family \t canonical_direction \t member_codes)
#   - canonical_direction: 该族的标准方向语义 = "谁是施动者(=head)", 如 head=visitor。
#   - member_codes: 按频次降序, **第一个 = 规范码 (canonical, 优先用它查)**;
#                   镜像/冗余、不该用的码以 '!' 前缀降级 (如 !Host_a_visit)。
#
# ⚠️ 规则顺序即优先级 (上面的先匹配)。绝大多数 CAMEO 关系都是 head=施动者(actor),
#    真正方向敏感的只有 visit (镜像对 Make/Host) 与 receive 语义, 已单列在最前。
# =====================================================================

# (family_key, canonical_direction, [keywords], {options})
#   options: {'demote': [被降级的精确码], 'canon': '强制规范码'}
FAMILY_RULES = [
    ('visit',            'head=visitor',       ['visit'],
        {'demote': ['Host_a_visit'], 'canon': 'Make_a_visit'}),
    ('receive_host',     'head=recipient',     ['receive_']),
    ('mediate',          'head=mediator',      ['mediat']),
    ('meet_negotiate',   'head=initiator',     ['negotiat', '_meet', 'meeting', 'third']),
    ('consult',          'head=actor',         ['consult', 'discuss_by_telephone']),
    ('appeal_request',   'head=requester',     ['appeal', 'request'],
        {'canon': 'Make_an_appeal_or_request'}),
    ('demand',           'head=demander',      ['demand'], {'canon': 'Demand'}),
    ('cooperate',        'head=actor',         ['cooperat', 'collaborat', 'share_intelligence']),
    ('sign_agreement',   'head=signatory',     ['sign', 'agreement', 'accord',
                                                'settle_dispute', 'truce', 'ceasefire']),
    ('praise_support',   'head=endorser',      ['praise', 'endorse', 'rally_support', 'optimistic']),
    ('criticize_accuse', 'head=accuser',       ['criticiz', 'denounce', 'accuse']),
    ('protest_dissent',  'head=protester',     ['protest', 'demonstrate_for', 'demonstrate_or',
                                                'riot', 'dissent', 'hunger_strike',
                                                'strike_or_boycott', 'rally_opposition']),
    ('mobilize_military', 'head=actor',        ['mobiliz', 'alert_status', 'demonstrate_military',
                                                'increase_armed', 'increase_military',
                                                'increase_police', 'demobiliz']),
    ('statement_comment', 'head=speaker',      ['statement', 'comment', 'defend_verbally',
                                                'decline_comment', 'acknowledge',
                                                'deny_responsibility', 'apolog', 'empath']),
    ('threaten',         'head=threatener',    ['threaten', 'ultimatum', 'coerce']),
    ('reject_refuse',    'head=actor',         ['reject', 'refuse', 'veto', 'defy',
                                                'obstruct', 'halt', '_block']),
    ('aid',              'head=provider',      ['aid', 'humanitarian', 'asylum', 'peacekeep',
                                                'provide_military_protection', 'provide_economic',
                                                'provide_aid', 'provide_military']),
    ('sanction_embargo', 'head=imposer',       ['embargo', 'boycott', 'sanction', 'blockade']),
    ('military_force',   'head=attacker',      ['military_force', 'armed_force', 'fight_with',
                                                'assault', 'bomb', 'weapon', 'occupy_territory',
                                                'kill', 'assassinat', 'artillery', 'aerial',
                                                'suicide', 'human_shield', 'repression', 'torture',
                                                'mass_killing', 'mass_expulsion', 'ethnic_cleansing',
                                                'nuclear', 'violen']),
    ('arrest_detain',    'head=enforcer',      ['arrest', 'detain', 'charge_with', 'confiscate',
                                                'expel_or_deport', 'deport', 'abduct', 'hijack',
                                                'hostage', 'ban_political', 'curfew', 'martial_law',
                                                'state_of_emergency', 'restrict', 'seize_or_damage',
                                                'destroy_property']),
    ('diplo_relations',  'head=actor',         ['diplomatic_relation', 'reduce_relation',
                                                'reduce_or_break', 'recognition', 'expel_or_withdraw']),
    ('yield_concede',    'head=actor',         ['yield', 'accede', 'forgive', 'grant',
                                                'return,_release', 'release_person',
                                                'release_property', 'release_of_persons',
                                                'ease_', 'allow_', 'retreat', 'surrender']),
    ('investigate',      'head=investigator',  ['investigat']),
    ('lawsuit_legal',    'head=plaintiff',     ['lawsuit', 'legal_action', 'judicial']),
    ('leadership_policy', 'head=actor',        ['leadership', 'regime', 'institution',
                                                'political_reform', 'policy', 'political_freedom',
                                                'political_dissent', 'political_part', 'rights',
                                                'international_involvement']),
    ('express_intent',   'head=actor',         ['express_intent', 'intent_to', 'consider_policy']),
    ('material_economic', 'head=actor',        ['economic', 'material']),
]
_FAMILY_DIR = {key: d for (key, d, _kw, *_o) in FAMILY_RULES}
_FAMILY_DIR['other'] = 'head=actor'


def assign_family(code):
    """把一个关系码确定性地归入第一个命中的关系族; 都不中 -> 'other'。"""
    low = code.lower()
    for entry in FAMILY_RULES:
        key, _dir, kws = entry[0], entry[1], entry[2]
        for kw in kws:
            if kw in low:
                return key
    return 'other'


def _rule_options(key):
    for entry in FAMILY_RULES:
        if entry[0] == key:
            return entry[3] if len(entry) > 3 else {}
    return {}


def build_relation_families(rel_freq, use_embedding=False):
    """返回 [(family, canonical_direction, [member_codes_排序后]), ...]，按族总频次降序。
    member_codes: 频次降序; canonical(规范码) 置首; 降级码以 '!' 前缀置尾。"""
    fam_members = defaultdict(list)   # family -> [code]
    for code in rel_freq:
        fam_members[assign_family(code)].append(code)

    # 可选 embedding: 把 'other' 里的关系按名字向量归并到最近的族 (阈值 0.45)。
    if use_embedding and fam_members.get('other'):
        _embedding_reassign(fam_members)

    rows = []
    for fam, codes in fam_members.items():
        opts = _rule_options(fam)
        demote = set(opts.get('demote', []))
        # 频次降序排
        codes_sorted = sorted(codes, key=lambda c: (-rel_freq[c], c))
        active = [c for c in codes_sorted if c not in demote]
        demoted = [c for c in codes_sorted if c in demote]
        # 规范码: 显式 canon 优先, 否则最高频的 active
        canon = opts.get('canon')
        if canon and canon in active:
            active = [canon] + [c for c in active if c != canon]
        members = active + [f'!{c}' for c in demoted]
        fam_freq = sum(rel_freq[c] for c in codes)
        rows.append((fam_freq, fam, _FAMILY_DIR.get(fam, 'head=actor'), members))
    rows.sort(key=lambda r: (-r[0], r[1]))
    return [(fam, d, members) for (_f, fam, d, members) in rows]


def _embedding_reassign(fam_members):
    """可选: 用 sentence-transformers 把 'other' 关系归并到最近族。无依赖则跳过。"""
    try:
        from sentence_transformers import SentenceTransformer
        import numpy as np
    except Exception:
        print('      [rel-embedding] 未安装 sentence-transformers, 跳过 (保持纯词法结果)。')
        return
    others = fam_members.get('other', [])
    targets = [f for f in fam_members if f != 'other']
    if not others or not targets:
        return
    model = SentenceTransformer('all-MiniLM-L6-v2')

    def humanize(code):
        return code.replace('_', ' ').replace(',', ' ').strip()

    # 族向量 = 该族成员名向量均值
    fam_vecs = {}
    for f in targets:
        embs = model.encode([humanize(c) for c in fam_members[f]], normalize_embeddings=True)
        fam_vecs[f] = np.asarray(embs).mean(axis=0)
    moved = 0
    keep = []
    for code in others:
        v = model.encode([humanize(code)], normalize_embeddings=True)[0]
        best_f, best_s = None, -1.0
        for f, fv in fam_vecs.items():
            s = float(np.dot(v, fv))
            if s > best_s:
                best_f, best_s = f, s
        if best_s >= 0.45:
            fam_members[best_f].append(code)
            moved += 1
        else:
            keep.append(code)
    fam_members['other'] = keep
    print(f'      [rel-embedding] 把 {moved} 个 other 关系归并到最近族 (cos>=0.45)。')


def main():
    ap = argparse.ArgumentParser(description='Build TKGQA filesystem knowledge base.')
    ap.add_argument('--input', default=os.path.join('data', 'full.txt'),
                    help='输入四元组 TSV（head\\trelation\\ttail\\tdate，无表头，UTF-8）')
    ap.add_argument('--out', default='database', help='输出知识库目录')
    ap.add_argument('--index-threshold', type=int, default=2000,
                    help='实体记录数超过该阈值才生成 INDEX.md（默认 2000）')
    ap.add_argument('--top-n', type=int, default=15,
                    help='INDEX.md 中高频关系/邻居各取前 N（默认 15）')
    ap.add_argument('--rel-embedding', action='store_true',
                    help='关系族投影时, 用 sentence-transformers 把 other 关系归并到最近族 '
                         '(可选, 无依赖则自动回退到纯词法)')
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

    # _relation_families.tsv : 关系族投影 (P1) —— NL 谓词 -> 族 -> 规范码 + 标准方向
    fam_rows = build_relation_families(rel_freq, use_embedding=args.rel_embedding)
    with open(os.path.join(out_dir, '_relation_families.tsv'), 'w', encoding='utf-8', newline='\n') as ff:
        ff.write('# family\tcanonical_direction\tmember_codes\n')
        ff.write('# member_codes: 空格分隔(关系码内含逗号,故不用逗号分隔); '
                 '频次降序, 第一个=规范码(优先用); !前缀=镜像冗余码(勿用)\n')
        for fam, direction, members in fam_rows:
            ff.write(f'{fam}\t{direction}\t{" ".join(members)}\n')
    n_fam = len(fam_rows)

    # ---- 5. 大实体导航包: INDEX.md (鸟瞰图) + by_year/ (时序钻取切片) [P2] ----
    # 论文式渐进披露: Agent 先读 INDEX.md(轻量地图: 哪些年/哪些关系/哪些邻居),
    # 再钻进相关年份的 by_year/<YYYY>.txt, 而不是面对一个 5 万行的 data.txt。
    # 纯附加: data.txt 原样保留, 旧的"awk data.txt"配方完全不受影响。
    print(f'[5/5] 为 {len(big_entities)} 个大实体(>{args.index_threshold} 条)'
          f'生成导航包 (INDEX.md + by_year/ 时序切片) ...')
    n_slices = 0
    for canonical in big_entities:
        rows = records[canonical]                # 已在第 3 步按日期升序
        rel_path = name_to_path[canonical]
        abs_dir = os.path.join(out_dir, *rel_path.split('/'))
        rel_cnt = Counter(r for (_, _, r, _) in rows)
        nbr_cnt = Counter(o for (_, _, _, o) in rows)
        dir_cnt = Counter(dir_ for (_, dir_, _, _) in rows)

        # 按年分组 (rows 已排序, 故每年的行也已排序)
        year_rows = defaultdict(list)
        for rec in rows:
            year_rows[rec[0][:4]].append(rec)

        # 落盘 by_year/<YYYY>.txt 时序切片
        by_year_dir = os.path.join(abs_dir, 'by_year')
        os.makedirs(by_year_dir, exist_ok=True)
        for y in sorted(year_rows):
            with open(os.path.join(by_year_dir, f'{y}.txt'), 'w',
                      encoding='utf-8', newline='\n') as yf:
                yf.writelines(f'{d}\t{dir_}\t{r}\t{o}\n'
                              for (d, dir_, r, o) in year_rows[y])
            n_slices += 1

        with open(os.path.join(abs_dir, 'INDEX.md'), 'w', encoding='utf-8', newline='\n') as mf:
            mf.write(f'# {canonical} — 导航地图 (INDEX)\n\n')
            mf.write(f'- 总事件数: {len(rows)}\n')
            mf.write(f'- 时间跨度: {rows[0][0]} ~ {rows[-1][0]}\n')
            mf.write(f"- 方向分布: 作为 head(>) {dir_cnt.get('>', 0)} 条 | "
                     f"作为 tail(<) {dir_cnt.get('<', 0)} 条\n\n")
            mf.write('## 如何钻取 (渐进披露)\n\n')
            mf.write('- 时间窗口/枢轴类问题: 先看下方"逐年地图"定位年份, 再 awk 对应的 '
                     '`by_year/<年>.txt` (只读相关年, 不要 awk 整个 data.txt)。\n')
            mf.write('- 跨多年或不确定年份: 仍可 awk `data.txt` 全量过滤 (结果一致, 切片只是省力)。\n')
            mf.write('- 关系/方向绑定: 参考下方"高频关系", 命中不了再回 '
                     '`_relation_families.tsv` 换同族关系码。\n\n')
            mf.write('## 逐年地图 (年 \t 事件数 \t 该年最高频关系)\n\n')
            for y in sorted(year_rows):
                yr_top = Counter(r for (_, _, r, _) in year_rows[y]).most_common(1)[0][0]
                mf.write(f'- {y}\t{len(year_rows[y])}\tby_year/{y}.txt\t{yr_top}\n')
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
    print(f'  关系族     : {n_fam} (-> _relation_families.tsv)')
    print(f'  大实体导航包: {len(big_entities)} 个 (INDEX.md + by_year/, 阈值 >{args.index_threshold})')
    print(f'  时序切片   : {n_slices} 个 by_year/<年>.txt')
    print(f'  耗时       : {dt:.1f}s')


README_LAYOUT = """TKGQA 文件系统知识库 —— 布局说明 (给 Agent)
=====================================================================

目录结构:
  database/
    _catalog.tsv          唯一入口：实体规范名 -> 安全目录路径
    _relations.txt        全部关系编码 + 频次（NL 短语 -> 关系编码映射用）
    _relation_families.tsv 关系族投影：NL 谓词 -> 族 -> 规范码 + 标准方向（绑定首选查这张表）
    _README_layout.txt    本文件
    entities/<桶>/<安全名>/
        data.txt          该实体全部相关四元组，已按日期升序（全量，永远可用）
        INDEX.md          仅 >{threshold} 条的大实体：导航地图（逐年地图/高频关系/高频邻居 + 钻取指引）
        by_year/<年>.txt  仅大实体：按年切片（INDEX.md 的钻取目标，省力，非必需）

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

_relation_families.tsv 列（关系绑定先查这张表，别再凭记忆猜关系码）:
    family \\t canonical_direction \\t member_codes
  * family            : 关系族名（如 visit / negotiate / appeal_request / criticize_accuse）。
  * canonical_direction: 该族标准方向 = 谁是施动者(=head)，如 head=visitor / head=actor。
  * member_codes      : 【空格分隔】(关系码内含逗号,故不能用逗号)；频次降序；
                        【第一个 = 规范码，优先用它】；'!' 前缀 = 镜像冗余码，勿用。
  用法: 先按 NL 谓词 grep 本表取族，拿规范码与方向，再去 data.txt 过滤。
    grep -i "visit" database/_relation_families.tsv
      -> visit \\t head=visitor \\t Make_a_visit !Host_a_visit
    规范码 = 第 3 列空格切分的第一个: awk -F'\\t' '/visit/{{split($3,a," "); print a[1]}}'
    含义: visit 一律用 Make_a_visit，访客=head(>)；绝不用 Host_a_visit。

分层导航 (大实体, 论文式渐进披露):
  大实体(>{threshold} 条)是一个"导航包": data.txt(全量) + INDEX.md(地图) + by_year/(切片)。
  推荐流程(省上下文、可回溯):
    1) cat INDEX.md          —— 鸟瞰: 哪些年有事件、各年最高频关系、Top 关系/邻居。
    2) 据"逐年地图"定位年份, 只 awk 相关切片:
         awk -F'\\t' '...' "database/<dir>/by_year/2010.txt"
    3) 跨多年/不确定 → 回退到全量 data.txt 过滤(结果一致, 切片只是省力)。
  ⛔ 铁律: first_last / before_last / after_first 永远只用全量 data.txt,
     禁止用 by_year/ —— first/last 是跨年全局极值, 切单年=错。
  ⛔ 切片空或不全 → 必须回退全量 data.txt 重查, 不要直接给"无相关事实"。
  小实体(无 INDEX.md): 直接 awk data.txt 即可(本就很小)。
  注: by_year/ 是【附加】结构, 不改变任何答案; 旧的"awk data.txt"配方继续有效。

重要约定:
  * 实体名与关系编码在库内一律用下划线。测试集标准答案用【空格】，
    抽出实体后输出前需把下划线还原为空格（Jack_Straw -> Jack Straw）。
  * 双向冗余：每条事实在 head 与 tail 两个目录各存一份，
    所以 tail 类问题（"谁访问了X"）只需读 X 的 data.txt，无需全库扫描。
  * 永远用 awk 过滤，绝不 cat 整个 data.txt 进上下文。
  * before_after 多答案题: 必须 sort -u 输出**全部**匹配行, 禁止只取前几个。
"""


if __name__ == '__main__':
    main()
