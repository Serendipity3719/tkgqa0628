RECORDS = []
with open('E:/RAG_Agent_Experiment/full.txt', 'r', encoding='utf-8-sig') as f:
    for line in f:
        parts = line.strip().split('\t')
        if len(parts) == 4:
            RECORDS.append({'subj': parts[0].replace('_',' '), 'rel': parts[1].replace('_',' '), 'obj': parts[2].replace('_',' '), 'date': parts[3]})

# Q37: "Which country did China study before the religion of China?"
# Truth: ['Japan']
# 'study' -> KB has no 'study' or 'research' relation
# But "China investigate Japan" exists! So LLM maps 'study' -> 'investigate'
# ref = 'religion of china' -> entity "Religion (China)" in KB
# Religion (China) as OBJ: China | Investigate | Religion (China) first at 2005-06-09
# So t_ref = 2005-06-09
# Before 2005-06-09, China investigate: Japan (2005-01-31, 2005-04-18, 2005-05-07)
print("=== Q37 Full Analysis ===")
china_inv_rel_china = [r for r in RECORDS if 'china' in r['subj'].lower() and 'investigate' in r['rel'].lower() and 'religion' in r['obj'].lower() and 'china' in r['obj'].lower()]
print(f"China investigate Religion(China): {len(china_inv_rel_china)}")
for r in china_inv_rel_china:
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")

# Also check investigate FROM religion china side
rel_china_inv = [r for r in RECORDS if 'religion' in r['subj'].lower() and 'china' in r['subj'].lower() and 'investigate' in r['rel'].lower()]
print(f"Religion(China) investigate*: {len(rel_china_inv)}")

t_ref_37 = china_inv_rel_china[0]['date'] if china_inv_rel_china else None
print(f"t_ref = {t_ref_37}")
if t_ref_37:
    china_study_before = [r for r in RECORDS if 'china' in r['subj'].lower() and r['subj'].lower() == 'china' and 'investigate' in r['rel'].lower() and r['date'] < t_ref_37]
    print(f"China investigate before {t_ref_37}: {len(china_study_before)}")
    for r in china_study_before:
        print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")
    entities = sorted(set(r['obj'] for r in china_study_before))
    print(f"Entities: {entities}")

# Q42: "Before the Asian Disaster Preparedness Centre, who did Thailand make optimistic comments about?"
# Truth: ['Citizen (Thailand)']
# Asian Disaster records: Thailand | Make optimistic comment | Asian Disaster Preparedness Center | 2005-01-21
# So t_ref = 2005-01-21
# Before 2005-01-21, Thailand optimistic about who?
print("\n=== Q42 Full Analysis ===")
thai_opt = [r for r in RECORDS if r['subj'].lower() == 'thailand' and 'optimistic' in r['rel'].lower() and r['date'] < '2005-01-21']
print(f"Thailand optimistic before 2005-01-21: {len(thai_opt)}")
for r in sorted(thai_opt, key=lambda x: x['date']):
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")
entities = sorted(set(r['obj'] for r in thai_opt))
print(f"Entities: {entities}")

# Q46: "Who attacked Iraq with small arms and light weapons after 9 August 2006?"
# Truth: ['Iran', 'Armed Rebel (Syria)', 'Israeli Defense Forces']
# V6 returns 200+ entities - because 'small arms' mapping issue
# 'fight' keyword - what does LLM parse for "attacked with small arms"?
# Likely: rel=['conventional military', 'conventional', 'military', 'unconventional', 'non-military']
# That's because "small arms" was NOT handled properly
# KB relation: "fight with small arms and light weapons"
# FIX: LLM should output rel=['small arms'] which maps to "fight with small arms and light weapons"
# But current prompt maps: "small arms / light weapons" -> rel keywords: ["small arms"]
# However V6 log shows: rel=['conventional military', 'conventional', 'military', 'unconventional', 'non-military']
# This means the LLM is not following the prompt correctly for Q46
print("\n=== Q46 Correct Manual Result ===")
small_arms_iraq_after = [r for r in RECORDS if 'small arms' in r['rel'].lower() and r['obj'].lower() == 'iraq' and r['date'] > '2006-08-09']
entities = sorted(set(r['subj'] for r in small_arms_iraq_after))
print(f"small arms vs Iraq (exact) after 2006-08-09: {entities}")

# Q93: Zawahiri issue - ref_date computation
# Current code: ref_recs = search_records(subj_kws=ref_kws, rel_kws=rel_kws) 
# Since Zawahiri has many 'criticize' records, it picks the first one (2005-10-24)
# which is BEFORE there are any citizen(saudi) criticize records
# FIX: When ref_kws are given and subj has specific OBJ context (obj_kws),
# we need to find when ref_entity did the SAME ACTION to the SAME OBJECT (obj_kws)
# not just any record of ref_entity
print("\n=== Q93 Ref Date Fix Analysis ===")
zawahiri_crit = [r for r in RECORDS if 'zawahiri' in r['subj'].lower() and 'criticize' in r['rel'].lower()]
print(f"All Zawahiri criticize (sorted): {len(zawahiri_crit)}")
for r in sorted(zawahiri_crit, key=lambda x: x['date']):
    print(f"  {r['date']} {r['obj']}")

# The correct ref_date for Q93 should be 2008-12-01 (Zawahiri criticize Citizen Saudi Arabia)
# If we restrict to ref_recs that ALSO match obj_kws=['saudi','citizen']:
zawahiri_crit_saudi_cit = [r for r in RECORDS if 'zawahiri' in r['subj'].lower() and 'criticize' in r['rel'].lower() and 'citizen' in r['obj'].lower() and 'saudi' in r['obj'].lower()]
print(f"Zawahiri criticize Citizen(Saudi): {len(zawahiri_crit_saudi_cit)}")
if zawahiri_crit_saudi_cit:
    t_ref = sorted(zawahiri_crit_saudi_cit, key=lambda x: x['date'])[0]['date']
    print(f"Correct t_ref: {t_ref}")

print("\n=== Summary of all 16 before_after wrong ===")
import json
with open('E:/RAG_Agent_Experiment/test.json', 'r', encoding='utf-8') as f:
    all_data = json.load(f)[:100]

ba_items = [(i, item) for i, item in enumerate(all_data) if item.get('qtype') == 'before_after']
print(f"Total before_after: {len(ba_items)}")
# List the answers that need entity list output
for i, item in ba_items:
    print(f"  Q{i+1}: answers={item['answers']}")
