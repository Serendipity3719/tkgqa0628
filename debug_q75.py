"""Debug Q75 and Q14 to understand why EPS hard filter isn't working."""
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Load KB directly
RECORDS = []
with open('full.txt', 'r', encoding='utf-8-sig') as f:
    for line in f:
        parts = line.strip().split('\t')
        if len(parts) == 4:
            subj, rel, obj, date = parts
            RECORDS.append({'subj': subj.replace('_',' '), 'rel': rel.replace('_',' '),
                            'obj': obj.replace('_',' '), 'date': date})
print(f"KB: {len(RECORDS)} records")

def search_records(subj_kws=None, rel_kws=None, obj_kws=None, time_prefix=None):
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

# Q75: "Who negotiated with the Thai military after Thailand?"
# LLM likely parses: rel=["negotiate"/"intent to meet or negotiate"], obj=["military","thailand"]
print("\n=== Q75 Analysis ===")
# What rel_kws does LLM produce? Let's test with likely values
rel_kws_q75 = ['negotiate', 'intent to meet or negotiate']
obj_kws_q75 = ['military', 'thailand']

# Hard filter: find valid subjs
obj_rel_recs = search_records(rel_kws=rel_kws_q75, obj_kws=obj_kws_q75)
print(f"obj+rel records (military+thailand + negotiate): {len(obj_rel_recs)}")
valid_subjs = set(r['subj'].lower() for r in obj_rel_recs)
print(f"Valid subjs count: {len(valid_subjs)}")
print(f"Sample valid subjs: {list(valid_subjs)[:10]}")

# GT entities
gt_q75 = ['National United Front for Democracy Against Dictatorship', 'Abhisit Vejjajiva', 'Worachai Hema', 'Protester (Thailand)']
for g in gt_q75:
    print(f"  GT '{g}' in valid_subjs: {g.lower() in valid_subjs}")

# Q14: "Before 25 April 2005, who used conventional military force against Iraq?"
print("\n=== Q14 Analysis ===")
rel_kws_q14 = ['Use conventional military force', 'conventional military force']
obj_kws_q14 = ['iraq']

obj_rel_recs14 = search_records(rel_kws=rel_kws_q14, obj_kws=obj_kws_q14)
print(f"obj+rel records (iraq + conventional military): {len(obj_rel_recs14)}")
valid_subjs14 = set(r['subj'].lower() for r in obj_rel_recs14)
print(f"Valid subjs count: {len(valid_subjs14)}")

gt_q14 = ['Iran', 'Commando (Iraq)']
for g in gt_q14:
    print(f"  GT '{g}' in valid_subjs: {g.lower() in valid_subjs14}")

# Check what rel_kws_exp would be for Q75
print("\n=== Q75 rel expansion ===")
ALL_RELATIONS = sorted(set(r['rel'] for r in RECORDS))
ALL_RELATIONS_LOWER = [r.lower() for r in ALL_RELATIONS]
negotiate_rels = [r for r in ALL_RELATIONS if 'negotiat' in r.lower()]
print("KB relations with 'negotiat':", negotiate_rels)

# Check what the actual obj looks like for Thai military
thai_mil_recs = search_records(obj_kws=['military', 'thailand'])
thai_mil_objs = set(r['obj'] for r in thai_mil_recs)
print(f"\nObjects matching 'military'+'thailand': {thai_mil_objs}")

# Check negotiate + thai military
neg_thai_mil = search_records(rel_kws=['negotiat'], obj_kws=['military', 'thailand'])
print(f"\nNegotiate + thai military records: {len(neg_thai_mil)}")
if neg_thai_mil:
    subjs = set(r['subj'] for r in neg_thai_mil)
    print(f"Subjs: {list(subjs)[:20]}")
