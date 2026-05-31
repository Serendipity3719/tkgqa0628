with open('full.txt', 'r', encoding='utf-8-sig') as f:
    rels = set()
    for line in f:
        parts = line.strip().split('\t')
        if len(parts) == 4:
            rels.add(parts[1].replace('_',' '))
print(f"Total relations: {len(rels)}")
for r in sorted(rels):
    print(r)
