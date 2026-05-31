RECORDS = []
with open('E:/RAG_Agent_Experiment/full.txt', 'r', encoding='utf-8-sig') as f:
    for line in f:
        parts = line.strip().split('\t')
        if len(parts) == 4:
            RECORDS.append({'rel': parts[1]})

ALL_RELATIONS = sorted(set(r['rel'] for r in RECORDS))
print('All 251 KB relations (processed, with spaces):')
for r in ALL_RELATIONS:
    processed = r.replace('_', ' ')
    print(f'  {processed}')
