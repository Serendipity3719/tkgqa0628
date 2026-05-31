RECORDS = []
with open('E:/RAG_Agent_Experiment/full.txt', 'r', encoding='utf-8-sig') as f:
    for line in f:
        parts = line.strip().split('\t')
        if len(parts) == 4:
            RECORDS.append({'rel': parts[1]})

ALL_RELATIONS = sorted(set(r['rel'] for r in RECORDS))
ALL_RELATIONS_LOWER = [r.lower() for r in ALL_RELATIONS]

print('Total KB relations:', len(ALL_RELATIONS))

# Show all relations (raw) - first 30
print('\nFirst 50 KB relations:')
for r in ALL_RELATIONS[:50]:
    print(' ', repr(r))

print('\n...')
print('\nRelations containing "visit":')
for r in ALL_RELATIONS:
    if 'visit' in r.lower():
        print(' ', repr(r))

print('\nRelations containing "small":')
for r in ALL_RELATIONS:
    if 'small' in r.lower():
        print(' ', repr(r))

print('\nRelations containing "unconventional":')
for r in ALL_RELATIONS:
    if 'unconventional' in r.lower():
        print(' ', repr(r))
