RECORDS = []
with open('E:/RAG_Agent_Experiment/full.txt', 'r', encoding='utf-8-sig') as f:
    for line in f:
        parts = line.strip().split('\t')
        if len(parts) == 4:
            RECORDS.append({'subj': parts[0].replace('_',' '), 'rel': parts[1].replace('_',' '), 'obj': parts[2].replace('_',' '), 'date': parts[3]})

from collections import Counter
rel_counts = Counter(r['rel'] for r in RECORDS)

# Check record counts for specific relations
target_rels = [
    'Use conventional military force',
    'Use unconventional violence',
    'fight with small arms and light weapons',
    'Use conventional military force',
    'Make optimistic comment',
    'Make pessimistic comment',
    'Criticize or denounce',
    'Praise or endorse',
    'Reject',
    'Accuse',
    'Express intent to meet or negotiate',
    'Make a visit',
    'Host a visit',
    'Express intent to cooperate',
    'Sign formal agreement',
    'Investigate',
]
for rel in target_rels:
    print(f'{rel_counts.get(rel, 0):6d}  {rel}')

print()
# Check: how many records match "conventional" and "military" separately vs together
conv_only = [r for r in RECORDS if 'conventional' in r['rel'].lower()]
mil_only = [r for r in RECORDS if 'military' in r['rel'].lower()]
conv_mil = [r for r in RECORDS if 'conventional military' in r['rel'].lower()]
print(f'conventional records: {len(conv_only)}')
print(f'military records: {len(mil_only)}')
print(f'conventional military records: {len(conv_mil)}')

# Examine Q46: small arms against Iraq after 9 Aug 2006
small_arms = [r for r in RECORDS if 'small arms' in r['rel'].lower() and 'iraq' in r['obj'].lower() and r['date'] > '2006-08-09']
print(f'\nsmall arms against Iraq after 2006-08-09: {len(small_arms)}')
for r in small_arms[:5]:
    print(f"  {r['subj']} | {r['rel']} | {r['obj']} | {r['date']}")

# Examine Q93: criticize saudi arabia citizen before zawahiri
crit_saudi = [r for r in RECORDS if 'criticize' in r['rel'].lower() and 'saudi' in r['obj'].lower()]
print(f'\ncriticize saudi: {len(crit_saudi)}')
for r in crit_saudi[:10]:
    print(f"  {r['subj']} | {r['rel']} | {r['obj']} | {r['date']}")

# Check Q8: seyoum mesfin 
seyoum = [r for r in RECORDS if 'seyoum' in r['subj'].lower()]
print(f'\nseyoum records: {len(seyoum)}')
for r in seyoum[:10]:
    print(f"  {r['subj']} | {r['rel']} | {r['obj']} | {r['date']}")
