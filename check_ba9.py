import json
RECORDS = []
with open('E:/RAG_Agent_Experiment/full.txt', 'r', encoding='utf-8-sig') as f:
    for line in f:
        parts = line.strip().split('\t')
        if len(parts) == 4:
            RECORDS.append({'subj': parts[0].replace('_',' '), 'rel': parts[1].replace('_',' '), 'obj': parts[2].replace('_',' '), 'date': parts[3]})

# Q34: "Before Oman, with which country did Thailand formally sign an agreement?"
# Thailand sign Oman: 2005-03-03 AND 2005-04-28
# The question "Before Oman" means before FIRST Thailand-Oman signing = 2005-03-03
# Before 2005-03-03, Thailand sign: ?
print("=== Q34 ===")
thai_sign_before = [r for r in RECORDS if r['subj'].lower() == 'thailand' and 'sign' in r['rel'].lower() and r['date'] < '2005-03-03']
print(f"Thailand sign before 2005-03-03: {len(thai_sign_before)}")
for r in sorted(thai_sign_before, key=lambda x: x['date']):
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")
entities = sorted(set(r['obj'] for r in thai_sign_before))
print(f"Entities: {entities}")

# Q75: "Who negotiated with the Thai military after Thailand?"
# Truth: ['National United Front for Democracy Against Dictatorship', 'Abhisit Vejjajiva', 'Worachai Hema', 'Protester (Thailand)']
# "Thai military" = Military (Thailand)  (note: not "Military Personnel (Thailand)")
# ref = "Thailand" -> when did Thailand negotiate? Very many records!
# "after Thailand" means after the LAST time Thailand negotiated? or first?
# Actually for before_after with ref, we need to find when Thailand (the plain entity) 
# did the SAME action as the question: negotiated with Military(Thailand)
# Or "after Thailand" = after the FIRST Thailand negotiation with Military(Thailand)?
print("\n=== Q75 ===")
thai_neg_mil = [r for r in RECORDS if r['subj'].lower() == 'thailand' and 'negotiate' in r['rel'].lower() and 'military' in r['obj'].lower() and 'thailand' in r['obj'].lower()]
print(f"Thailand negotiate Military(Thailand): {len(thai_neg_mil)}")
mil_neg_thai = [r for r in RECORDS if 'military' in r['subj'].lower() and 'thailand' in r['subj'].lower() and 'negotiate' in r['rel'].lower() and 'thailand' in r['obj'].lower()]
print(f"Military(Thailand) negotiate Thailand: {len(mil_neg_thai)}")

# Broader: when did Thailand negotiate with Thai military? Or military with Thailand?
thai_any_mil = [r for r in RECORDS if r['subj'].lower() == 'thailand' and ('military' in r['obj'].lower() and 'thailand' in r['obj'].lower())]
mil_any_thai = [r for r in RECORDS if ('military' in r['subj'].lower() and 'thailand' in r['subj'].lower()) and r['obj'].lower() == 'thailand']
print(f"Thailand * Military(Thailand): {len(thai_any_mil)}")
print(f"Military(Thailand) * Thailand: {len(mil_any_thai)}")
for r in sorted(thai_any_mil + mil_any_thai, key=lambda x: x['date'])[:5]:
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")

# Maybe "after Thailand" = after Thailand itself (as ref entity, broader search)
# Find the t_ref = first time Thailand appeared in negotiate role with military
# Or more likely, the question is asking:
# "Who (besides Thailand) negotiated with Military(Thailand) AFTER Thailand did?"
# So find t_ref = when Thailand negotiate Military(Thailand)
# Then find who else negotiated with Military(Thailand) after t_ref
military_th_obj = [r for r in RECORDS if 'military' in r['obj'].lower() and 'thailand' in r['obj'].lower() and 'negotiate' in r['rel'].lower()]
print(f"\nRecords with Military(Thailand) as OBJ and negotiate rel: {len(military_th_obj)}")
for r in sorted(military_th_obj, key=lambda x: x['date'])[:10]:
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")

# Check ref approach: when does Thailand appear in relation to Thai military in negotiate
# Ref entity = "Thailand", context = Military(Thailand) as obj_kws
thai_ref_neg = [r for r in RECORDS if r['subj'].lower() == 'thailand' and 'negotiate' in r['rel'].lower()]
thai_ref_neg.sort(key=lambda x: x['date'])
print(f"\nThailand negotiate (first few):")
for r in thai_ref_neg[:5]:
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")
# With Thai military in obj:
thai_neg_with_mil = [r for r in thai_ref_neg if 'military' in r['obj'].lower()]
print(f"Thailand negotiate with military*: {len(thai_neg_with_mil)}")
for r in sorted(thai_neg_with_mil, key=lambda x: x['date'])[:5]:
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")

# Q95: Cambodia host Yang - find ref_date
print("\n=== Q95 ===")
camb_yang = [r for r in RECORDS if ('cambodia' in r['subj'].lower() and 'host' in r['rel'].lower() and 'yang' in r['obj'].lower())
             or ('cambodia' in r['subj'].lower() and 'yang' in r['obj'].lower())]
print(f"Cambodia * Yang: {len(camb_yang)}")
for r in sorted(camb_yang, key=lambda x: x['date']):
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")
if camb_yang:
    t_ref = sorted(camb_yang, key=lambda x: x['date'])[0]['date']
    # who hosted Yang before t_ref?
    host_yang = [r for r in RECORDS if ('host' in r['rel'].lower() or 'visit' in r['rel'].lower()) 
                 and ('yang' in r['obj'].lower() or 'yang' in r['subj'].lower())
                 and r['date'] < t_ref]
    host_yang_entities = sorted(set(r['subj'] for r in host_yang if 'yang' in r['obj'].lower()))
    print(f"Hosts of Yang before {t_ref}: {host_yang_entities}")
