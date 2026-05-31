"""Check KB for specific failing cases to understand root causes."""

with open('full.txt', 'r', encoding='utf-8-sig') as f:
    recs = []
    for line in f:
        parts = line.strip().split('\t')
        if len(parts) == 4:
            recs.append({'s': parts[0].replace('_',' '), 'r': parts[1].replace('_',' '), 'o': parts[2].replace('_',' '), 'd': parts[3]})

print(f"Total records: {len(recs)}")

print('\n=== Q11: Criminal (Somalia) threaten China ===')
# KB has "Threaten with military force" as "coerce"?
hits = [r for r in recs if 'criminal' in r['s'].lower() and 'somalia' in r['s'].lower()]
print(f"Criminal(Somalia) records: {len(hits)}")
for r in sorted(hits, key=lambda x: x['d'])[:10]:
    print(f"  {r['s']} | {r['r']} | {r['o']} | {r['d']}")

print('\n=== Q11b: What KB relation = "threaten"? ===')
hits = [r for r in recs if 'threat' in r['r'].lower() or 'coerce' in r['r'].lower() or 'threaten' in r['r'].lower()]
rels = set(r['r'] for r in hits)
print("Relations with threat/coerce:", sorted(rels))

print('\n=== Q88: Donald Rumsfeld KB records ===')
hits = [r for r in recs if 'rumsfeld' in r['s'].lower()]
print(f"Rumsfeld as subj: {len(hits)}")
for r in sorted(hits, key=lambda x: x['d'])[:15]:
    print(f"  {r['s']} | {r['r']} | {r['o']} | {r['d']}")

print('\n=== Q22: Agence France-Presse in KB ===')
hits = [r for r in recs if 'agence france' in r['s'].lower()]
print(f"Agence France-Presse as subj: {len(hits)}")
for r in sorted(hits, key=lambda x: x['d'])[:10]:
    print(f"  {r['s']} | {r['r']} | {r['o']} | {r['d']}")

print('\n=== Q70: Council of Advisors / Cabinet US threaten Thailand ===')
hits = [r for r in recs if 'cabinet' in r['s'].lower() and 'united states' in r['s'].lower() and 'thailand' in r['o'].lower()]
print(f"Cabinet(US) + Thailand: {len(hits)}")
for r in sorted(hits, key=lambda x: x['d'])[:10]:
    print(f"  {r['s']} | {r['r']} | {r['o']} | {r['d']}")
hits2 = [r for r in recs if 'council' in r['s'].lower() and 'united states' in r['s'].lower()]
print(f"\nCouncil(US) as subj: {len(hits2)}")
for r in sorted(hits2, key=lambda x: x['d'])[:5]:
    print(f"  {r['s']} | {r['r']} | {r['o']} | {r['d']}")

print('\n=== Q75: Thai military (Military Personnel Thailand) negotiate ===')
hits = [r for r in recs if 'military personnel' in r['o'].lower() and 'thailand' in r['o'].lower()]
print(f"Military Personnel (Thailand) as obj: {len(hits)}")
for r in sorted(hits, key=lambda x: x['d'])[:8]:
    print(f"  {r['s']} | {r['r']} | {r['o']} | {r['d']}")

# What is the Thailand entity for "Thai military"
hits2 = [r for r in recs if 'military' in r['o'].lower() and 'thailand' in r['o'].lower()]
ents = set(r['o'] for r in hits2)
print(f"\nMilitary Thailand entities:", sorted(ents))

print('\n=== Q55: "negotiate" -> KB relation name ===')
hits = [r for r in recs if 'engage in negotiation' in r['r'].lower()]
print(f"'Engage in negotiation' records: {len(hits)}")
for r in sorted(hits, key=lambda x: x['d'])[:5]:
    print(f"  {r['s']} | {r['r']} | {r['o']} | {r['d']}")

print('\n=== Q46: small arms KB relation ===')
hits = [r for r in recs if 'small arms' in r['r'].lower()]
print(f"'small arms' records: {len(hits)}")
for r in sorted(hits, key=lambda x: x['d'])[:3]:
    print(f"  {r['s']} | {r['r']} | {r['o']} | {r['d']}")

# Show the EXACT relation name for small arms
rels = set(r['r'] for r in hits)
print("Small arms relations:", rels)

print('\n=== Q12/14: conventional military force KB relation ===')
hits = [r for r in recs if 'conventional military' in r['r'].lower() or 'Use conventional military force' in r['r']]
rels = set(r['r'] for r in hits)
print("Conventional military relations:", rels)

print('\n=== Q36: Thailand first appears as obj of Malaysian FM praise ===')
hits = [r for r in recs if 'foreign affairs' in r['s'].lower() and 'malaysia' in r['s'].lower() and 'praise' in r['r'].lower()]
hits.sort(key=lambda x: x['d'])
print(f"Total Foreign Affairs (Malaysia) praise: {len(hits)}")
for r in hits:
    print(f"  {r['s']} | {r['o']} | {r['d']}")

# Thailand first appears
th_hits = [r for r in hits if 'thailand' in r['o'].lower()]
print(f"\nThailand appears: {[(r['o'], r['d']) for r in th_hits]}")

print('\n=== Q42: Asian Disaster Preparedness Centre in KB ===')
hits = [r for r in recs if 'asian disaster' in r['s'].lower() or 'asian disaster' in r['o'].lower()]
print(f"Asian Disaster Preparedness Centre: {len(hits)}")
for r in hits[:5]:
    print(f"  {r['s']} | {r['r']} | {r['o']} | {r['d']}")

print('\n=== Q61: Sudanese Police in KB ===')
hits = [r for r in recs if 'sudanese' in r['s'].lower() and 'police' in r['s'].lower()]
print(f"Sudanese Police as subj: {len(hits)}")
for r in hits[:5]:
    print(f"  {r['s']} | {r['r']} | {r['o']} | {r['d']}")

hits2 = [r for r in recs if 'police' in r['s'].lower() and 'sudan' in r['s'].lower()]
print(f"Police(Sudan) as subj: {len(hits2)}")
for r in sorted(hits2, key=lambda x: x['d'])[:5]:
    print(f"  {r['s']} | {r['r']} | {r['o']} | {r['d']}")

print('\n=== Q64: Iraq praise member of parliament Iran ===')
hits = [r for r in recs if 'iraq' in r['s'].lower() and 'praise' in r['r'].lower() and 'member' in r['o'].lower() and 'iran' in r['o'].lower()]
print(f"Iraq+praise+member(Iran): {len(hits)}")
for r in hits[:5]:
    print(f"  {r['s']} | {r['r']} | {r['o']} | {r['d']}")

hits2 = [r for r in recs if 'iraq' in r['s'].lower() and 'praise' in r['r'].lower() and 'parliament' in r['o'].lower()]
print(f"Iraq+praise+parliament: {len(hits2)}")
for r in hits2[:5]:
    print(f"  {r['s']} | {r['r']} | {r['o']} | {r['d']}")
