"""Debug Q73 and Q95 pipeline."""
import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Simulate the agent pipeline for Q73 and Q95
RECORDS = []
with open('full.txt', 'r', encoding='utf-8-sig') as f:
    for line in f:
        parts = line.strip().split('\t')
        if len(parts) == 4:
            subj, rel, obj, date = parts
            RECORDS.append({'subj': subj.replace('_',' '), 'rel': rel.replace('_',' '),
                            'obj': obj.replace('_',' '), 'date': date})

def search(subj_kws=None, rel_kws=None, obj_kws=None, time_prefix=None):
    results = []
    for r in RECORDS:
        if time_prefix and not r['date'].startswith(time_prefix): continue
        if subj_kws:
            sl = r['subj'].lower()
            if not all(kw.lower() in sl for kw in subj_kws): continue
        if rel_kws:
            rl = r['rel'].lower()
            if not any(kw.lower() in rl for kw in rel_kws): continue
        if obj_kws:
            ol = r['obj'].lower()
            if not all(kw.lower() in ol for kw in obj_kws): continue
        results.append(r)
    return results

def search_exact_rel(subj_kws=None, rel_exact=None, obj_kws=None):
    results = []
    for r in RECORDS:
        if subj_kws:
            sl = r['subj'].lower()
            if not all(kw.lower() in sl for kw in subj_kws): continue
        if rel_exact and r['rel'].lower() != rel_exact.lower(): continue
        if obj_kws:
            ol = r['obj'].lower()
            if not all(kw.lower() in ol for kw in obj_kws): continue
        results.append(r)
    return results

print("=== Q73 equal_multi debug ===")
print("Q: Who did Ethiopia use conventional military force against on the same day as the Hizbul Islam fighter?")
print("GT: Al-Shabaab")
print()

# After FIX GG: ref_kws=['hizbul', 'islam'] (fighter removed)
ref_kws = ['hizbul', 'islam']
subj_kws = ['ethiopia']
rel_kws = ['conventional military']
obj_kws = []

print("Step 1: find_ref_date_contextual")
print(f"  ref_kws={ref_kws}, subj_kws={subj_kws}, rel_kws={rel_kws}")

# Level 2a: subj+rel+ref
l2a = search(subj_kws=subj_kws, rel_kws=rel_kws, obj_kws=ref_kws)
l2a += search(subj_kws=ref_kws, rel_kws=rel_kws, obj_kws=subj_kws)
print(f"  Level 2a (subj+rel+ref): {len(l2a)} records")
for r in l2a:
    print(f"    {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")

# The issue: Level 2a finds Ethiopia | conv military | Combatant (Hizbul Islam)
# This is the MAIN event, not the ref event
# ref_anchor_rec = this record, ref_prefix = '2010-03-16'
# Then same_window_all searches Ethiopia+conv military on 2010-03-16
# → finds Al-Shabaab AND Combatant (Hizbul Islam)
# → excludes Hizbul Islam → returns Al-Shabaab ✓

if l2a:
    l2a.sort(key=lambda x: x['date'])
    ref_anchor_rec = l2a[0]
    ref_prefix = ref_anchor_rec['date'][:10]  # same_day=True → day-level
    print(f"  ref_anchor_rec: {ref_anchor_rec['date']} {ref_anchor_rec['subj']} | {ref_anchor_rec['rel']} | {ref_anchor_rec['obj']}")
    print(f"  ref_prefix: {ref_prefix}")
    
    # same_window_all
    same_window = search(subj_kws=subj_kws, rel_kws=rel_kws, time_prefix=ref_prefix)
    print(f"  same_window (Ethiopia+conv military on {ref_prefix}): {len(same_window)}")
    for r in same_window:
        print(f"    {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")
    
    # Exclude ref_kws entities
    entities = set()
    for r in same_window:
        if any(kw.lower() in r['subj'].lower() for kw in ref_kws) or \
           any(kw.lower() in r['obj'].lower() for kw in ref_kws):
            print(f"    EXCLUDED (ref): {r['obj']}")
            continue
        if subj_kws and all(kw.lower() in r['subj'].lower() for kw in subj_kws):
            entities.add(r['obj'])
    print(f"  Final entities: {sorted(entities)}")

print()
print("=== Q95 before_after debug ===")
print("Q: Who hosted the visit of Yang Hyong Sop before Cambodia did?")
print("GT: ['South Africa', 'China', 'Angola', 'Norodom Sihanouk']")
print()

# After FIX HH: obj_kws=['yang hyong sop'] (no change needed)
# visit_direction='host' (because 'hosted' in question)
# ref_kws=['cambodia']
# obj_kws=['yang hyong sop']
# subj_kws=[]

ref_kws_95 = ['cambodia']
obj_kws_95 = ['yang hyong sop']
subj_kws_95 = []
rel_kws_95 = ['visit']

print("Step 1: find_ref_date_contextual")
print(f"  ref_kws={ref_kws_95}, obj_kws={obj_kws_95}, subj_kws={subj_kws_95}")

# Level 2b: obj_kws present
l2b = search(subj_kws=ref_kws_95, rel_kws=rel_kws_95, obj_kws=obj_kws_95)
print(f"  Level 2b (ref+rel+obj): {len(l2b)} records")
for r in l2b:
    print(f"    {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")

if l2b:
    l2b.sort(key=lambda x: x['date'])
    ref_date = l2b[-1]['date']  # use_first=True → first date
    # Wait: find_ref_date_contextual uses use_first=True for before_after
    # So ref_date = l2b[0]['date'] = first date
    ref_date_first = l2b[0]['date']
    ref_date_last = l2b[-1]['date']
    print(f"  ref_date (first): {ref_date_first}")
    print(f"  ref_date (last): {ref_date_last}")
    
    # The before_after code calls find_ref_date_contextual with use_first=True
    # So ref_date = 2012-10-20 (only one record)
    ref_date = ref_date_first
    
    print(f"\nStep 2: all_side search")
    print(f"  visit_direction='host', obj_kws={obj_kws_95}")
    
    # FIX CC: search_records_exact_rel(rel_exact='Host a visit', obj_kws=obj_kws_95)
    all_side = search_exact_rel(rel_exact='Host a visit', obj_kws=obj_kws_95)
    print(f"  Host a visit + yang hyong sop: {len(all_side)} records")
    for r in sorted(all_side, key=lambda x: x['date']):
        print(f"    {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")
    
    # Filter before ref_date, exclude ref entity
    side = [r for r in all_side if r['date'] < ref_date
            and not any(kw.lower() in r['subj'].lower() for kw in ref_kws_95)
            and not any(kw.lower() in r['obj'].lower() for kw in ref_kws_95)]
    print(f"\n  After filter (before {ref_date}, excl Cambodia): {len(side)} records")
    for r in sorted(side, key=lambda x: x['date']):
        print(f"    {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")
    
    # Extract entities
    all_entities = sorted(set(r['subj'] for r in side))
    print(f"\n  all_entities: {all_entities}")
    
    # EPS filter: obj_kws=['yang hyong sop'], no subj_kws
    # Hard filter: obj+rel → find all valid subjs
    # search(rel_kws=['visit'], obj_kws=['yang hyong sop'])
    obj_rel_recs = search(rel_kws=['visit'], obj_kws=['yang hyong sop'])
    valid_subjs = set(r['subj'].lower() for r in obj_rel_recs)
    print(f"\n  EPS valid_subjs (rel+obj): {sorted(valid_subjs)}")
    filtered = [e for e in all_entities if e.lower() in valid_subjs]
    print(f"  EPS filtered: {filtered}")
