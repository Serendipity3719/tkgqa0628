import json
RECORDS = []
with open('E:/RAG_Agent_Experiment/full.txt', 'r', encoding='utf-8-sig') as f:
    for line in f:
        parts = line.strip().split('\t')
        if len(parts) == 4:
            RECORDS.append({'subj': parts[0].replace('_',' '), 'rel': parts[1].replace('_',' '), 'obj': parts[2].replace('_',' '), 'date': parts[3]})

with open('E:/RAG_Agent_Experiment/test.json', 'r', encoding='utf-8') as f:
    all_data = json.load(f)[:100]

# Q75: "Who negotiated with the Thai military after Thailand?"
# Truth: ['National United Front for Democracy Against Dictatorship', 'Abhisit Vejjajiva', 'Worachai Hema', 'Protester (Thailand)']
# Military(Thailand) = Military Personnel (Thailand) or Military (Thailand)?
# DB shows "Military Personnel (Thailand)" matches
# ref = "Thailand" (exact entity)
# What does Thailand do with Military Personnel (Thailand)? 
# OR what does Military Personnel (Thailand) do with Thailand?
# Find when Thailand did negotiate with Military Personnel (Thailand):
print("=== Q75 Deep Dive ===")
# ref: Thailand negotiate OR with Military(Thailand)
# Key insight: "after Thailand" = after Thailand negotiated with Thai military OR 
# after Thailand (as ref entity) first appeared doing the relevant action
# Check: Military(Thailand) negotiate Thailand
mil_neg_tha = [r for r in RECORDS if 'military' in r['subj'].lower() and 'thailand' in r['subj'].lower() 
               and 'negotiate' in r['rel'].lower() and r['obj'].lower() == 'thailand']
print(f"Military(Thailand) negotiate Thailand: {len(mil_neg_tha)}")
for r in sorted(mil_neg_tha, key=lambda x: x['date']):
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")

# Check: Thailand negotiate with Military(Thailand) (as obj)
thai_neg_mil_obj = [r for r in RECORDS if r['subj'].lower() == 'thailand' 
                    and 'negotiate' in r['rel'].lower()
                    and 'military' in r['obj'].lower() and 'thailand' in r['obj'].lower()]
print(f"Thailand negotiate Military(Thailand): {len(thai_neg_mil_obj)}")

# Broader: find t_ref for Thailand -> any negotiate involving Thai military?
# Military personnel (Thailand) negotiate: 14 records as subj. With Thailand?
mil_th_neg_all = [r for r in RECORDS if 'military' in r['subj'].lower() and 'thailand' in r['subj'].lower() 
                  and 'negotiate' in r['rel'].lower()]
print(f"\nAll Military*(Thailand) negotiate records:")
for r in sorted(mil_th_neg_all, key=lambda x: x['date']):
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")

# The truth entities [NUFDD, Abhisit Vejjajiva, Worachai Hema, Protester(Thailand)]
# These appear in which records?
for ent in ['national united front', 'abhisit', 'worachai', 'protester']:
    recs = [r for r in RECORDS if ent in r['subj'].lower() and 'military' in r['obj'].lower() and 'thailand' in r['obj'].lower() and 'negotiate' in r['rel'].lower()]
    print(f"{ent} negotiate Military(Thailand): {len(recs)}")
    for r in sorted(recs, key=lambda x: x['date'])[:3]:
        print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")

# So the correct search: who (besides Thailand) negotiate Military(Thailand)?
# ref_date = when did Thailand first do something with Military(Thailand) in negotiate context
# Let's try: find Thailand records involving Military(Thailand) in any role
thai_mil_th = [r for r in RECORDS if (r['subj'].lower() == 'thailand' and 'military' in r['obj'].lower() and 'thailand' in r['obj'].lower()) 
               or ('military' in r['subj'].lower() and 'thailand' in r['subj'].lower() and r['obj'].lower() == 'thailand')]
thai_mil_th_neg = [r for r in thai_mil_th if 'negotiate' in r['rel'].lower()]
print(f"\nThailand<->Military(Thailand) negotiate: {len(thai_mil_th_neg)}")
for r in sorted(thai_mil_th_neg, key=lambda x: x['date']):
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")

# ref date appears to be 2010-03 or similar
# After t_ref, who negotiated with Military(Thailand)?
mil_obj_all_neg = [r for r in RECORDS if 'military' in r['obj'].lower() and 'thailand' in r['obj'].lower() and 'negotiate' in r['rel'].lower()]
print(f"\nAll records with Military*(Thailand) as OBJ and negotiate:")
for r in sorted(mil_obj_all_neg, key=lambda x: x['date']):
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")

print("\n=== Q95 extra ===")
# Cambodia host Yang: 2012-10-20
# Hosts before: Angola, Boris Vyacheslavovich Gryzlov, China, Norodom Sihanouk, South Africa
# Truth: ['South Africa', 'China', 'Angola', 'Norodom Sihanouk']
# Boris Gryzlov is extra FP. Let's see why he's in the list
boris_yang = [r for r in RECORDS if 'boris' in r['subj'].lower() and 'yang' in r['obj'].lower()]
print(f"Boris * Yang: {len(boris_yang)}")
for r in boris_yang:
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")
# So Boris appears as a host? No, probably as a visitor...
# The ground truth doesn't include Boris, so we need exact 'host' rel
host_yang = [r for r in RECORDS if 'host' in r['rel'].lower() and 'yang' in r['obj'].lower() and r['date'] < '2012-10-20']
print(f"\nHost a visit Yang before 2012-10-20:")
for r in sorted(host_yang, key=lambda x: x['date']):
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")
