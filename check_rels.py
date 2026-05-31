import sys
RECORDS = []
with open('E:/RAG_Agent_Experiment/full.txt', 'r', encoding='utf-8-sig') as f:
    for line in f:
        parts = line.strip().split('\t')
        if len(parts) == 4:
            RECORDS.append({'rel': parts[1]})

ALL_RELATIONS = sorted(set(r['rel'] for r in RECORDS))

print('Relations containing "conventional":')
for r in ALL_RELATIONS:
    if 'conventional' in r.lower():
        print(' ', r)

print()
print('Relations containing "small arm":')
for r in ALL_RELATIONS:
    if 'small arm' in r.lower():
        print(' ', r)

print()
print('Relations containing "intent to meet":')
for r in ALL_RELATIONS:
    if 'intent to meet' in r.lower():
        print(' ', r)

print()
print('Relations containing "reject":')
for r in ALL_RELATIONS:
    if 'reject' in r.lower():
        print(' ', r)

print()
print('Relations containing "accuse":')
for r in ALL_RELATIONS:
    if 'accuse' in r.lower():
        print(' ', r)
