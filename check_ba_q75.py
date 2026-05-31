import json
RECORDS = []
with open('E:/RAG_Agent_Experiment/full.txt', 'r', encoding='utf-8-sig') as f:
    for line in f:
        parts = line.strip().split('\t')
        if len(parts) == 4:
            RECORDS.append({'subj': parts[0].replace('_',' '), 'rel': parts[1].replace('_',' '), 'obj': parts[2].replace('_',' '), 'date': parts[3]})

# Q75: "Who negotiated with the Thai military after Thailand?"
# Truth: ['National United Front for Democracy Against Dictatorship', 'Abhisit Vejjajiva', 'Worachai Hema', 'Protester (Thailand)']
# Key insight from data:
# - Military(Thailand) negotiate Thailand: first at 2006-08-29
# - "after Thailand" ref: t_ref = 2006-08-29 (first time military(Thailand) negotiated with Thailand)
# - After 2006-08-29, who negotiate Military(Thailand) as OBJ?
# Records: 2008-05-09 Citizen(Thailand), 2008-08-05 Cambodia, 2008-09-08/09 Citizen(Thailand),
#          2010-02-10 Citizen(Thailand), 2011-08-10 Yuthasak, 2011-12-17/19 Police(Cambodia)
#          2013-11-29 Protester(Thailand)
# But truth is: NUFDD, Abhisit, Worachai, Protester(Thailand) - NOT Citizen, Cambodia

# So the actual KB must use DIFFERENT entity names for the truth entities
# Let's search for each truth entity
print("=== Q75: Finding truth entities ===")
for ent in ['national united front for democracy against dictatorship', 'abhisit vejjajiva', 'worachai hema', 'protester (thailand)']:
    recs = [r for r in RECORDS if ent.lower() in r['subj'].lower()]
    print(f"\n'{ent}' as subj: {len(recs)}")
    mil_recs = [r for r in recs if 'military' in r['obj'].lower() and 'thailand' in r['obj'].lower()]
    print(f"  ...with Military(Thailand) as obj: {len(mil_recs)}")
    for r in sorted(mil_recs, key=lambda x: x['date'])[:5]:
        print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")

# Check all negotiate records involving 'military (thailand)' (not military personnel)
print("\n=== Military (Thailand) vs Military Personnel (Thailand) ===")
mil_recs = [r for r in RECORDS if 'military (thailand)' in r['obj'].lower() or 'military (thailand)' in r['subj'].lower()]
print(f"Records with 'Military (Thailand)': {len(mil_recs)}")
for r in sorted(mil_recs, key=lambda x: x['date'])[:10]:
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")

# Now check: where do NUFDD, Abhisit, Worachai appear in relation to Military entities?
print("\n=== NUFDD negotiate Military ===")
nufdd = [r for r in RECORDS if 'national united front' in r['subj'].lower() and 'negotiate' in r['rel'].lower()]
print(f"NUFDD negotiate: {len(nufdd)}")
for r in sorted(nufdd, key=lambda x: x['date'])[:10]:
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")

print("\n=== Abhisit negotiate Military ===")
abhisit = [r for r in RECORDS if 'abhisit' in r['subj'].lower() and 'negotiate' in r['rel'].lower()]
print(f"Abhisit negotiate: {len(abhisit)}")
for r in sorted(abhisit, key=lambda x: x['date'])[:10]:
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")

print("\n=== Worachai negotiate ===")
worachai = [r for r in RECORDS if 'worachai' in r['subj'].lower() and 'negotiate' in r['rel'].lower()]
print(f"Worachai negotiate: {len(worachai)}")
for r in sorted(worachai, key=lambda x: x['date'])[:10]:
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")

print("\n=== Q75: KB records with ref 'Thailand' + obj 'military' + negotiate ===")
# The reference entity is 'Thailand', and the question asks who negotiated with 'Thai military'
# The Solver should:
# 1. Find when 'Thailand' itself negotiated with 'Military*(Thailand)' 
#    (or Military*(Thailand) negotiated with Thailand) -> t_ref
# 2. After t_ref, find who negotiated with Military*(Thailand)
# From data: first Thailand<->Military*(Thailand) negotiate: 2006-08-29
# After 2006-08-29, who negotiate Military*(Thailand) as OBJ (excluding Thailand, Cambodia):
after_t = [r for r in RECORDS if 'military' in r['obj'].lower() and 'thailand' in r['obj'].lower() 
           and 'negotiate' in r['rel'].lower() and r['date'] > '2006-08-29'
           and 'thailand' not in r['subj'].lower() and 'cambodia' not in r['subj'].lower()]
print(f"After 2006-08-29, non-Thailand/Cambodia negotiate Military*(Thailand): {len(after_t)}")
for r in sorted(after_t, key=lambda x: x['date']):
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")
