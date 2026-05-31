RECORDS = []
with open('E:/RAG_Agent_Experiment/full.txt', 'r', encoding='utf-8-sig') as f:
    for line in f:
        parts = line.strip().split('\t')
        if len(parts) == 4:
            RECORDS.append({'subj': parts[0].replace('_',' '), 'rel': parts[1].replace('_',' '), 'obj': parts[2].replace('_',' '), 'date': parts[3]})

# Q93: "Who criticised the citizens of Saudi Arabia before Zawahiri?"
# Truth: ['Iran', 'Islamic Preacher (Saudi Arabia)', 'Royal Administration (Saudi Arabia)']
# Zawahiri criticize saudi arabia citizen: 2008-12-01
# So we need criticize + citizen (saudi arabia) before 2008-12-01

zawahiri_recs = [r for r in RECORDS if 'zawahiri' in r['subj'].lower() and 'criticize' in r['rel'].lower()]
print('Zawahiri criticize records:')
for r in zawahiri_recs:
    print(f"  {r['subj']} | {r['rel']} | {r['obj']} | {r['date']}")

ref_date = zawahiri_recs[0]['date'] if zawahiri_recs else None
print(f'\nRef date: {ref_date}')

crit_citizen_saudi = [r for r in RECORDS if 'criticize' in r['rel'].lower() and 'citizen' in r['obj'].lower() and 'saudi' in r['obj'].lower()]
print(f'\nCriticize citizen (saudi arabia): {len(crit_citizen_saudi)}')
for r in crit_citizen_saudi:
    print(f"  {r['subj']} | {r['rel']} | {r['obj']} | {r['date']}")

if ref_date:
    before = [r for r in crit_citizen_saudi if r['date'] < ref_date]
    print(f'\nBefore {ref_date}: {len(before)}')
    for r in before:
        print(f"  {r['subj']} | {r['rel']} | {r['obj']} | {r['date']}")

print()
# Q18: "Who praised Kuwait before Nuri al-Maliki?"
# Truth: ['Presidential Family (United States)', 'Shaukat Aziz', 'Sudan', 'Pervez Musharraf', 'Saud bin Faisal bin Abdul-Aziz', 'Jack Straw', 'Japan']
# Model gave 13 entities, truth has 7
nuri_praise_kuwait = [r for r in RECORDS if 'nuri' in r['subj'].lower() and 'praise' in r['rel'].lower() and 'kuwait' in r['obj'].lower()]
print(f'Nuri al-Maliki praise Kuwait records:')
for r in nuri_praise_kuwait:
    print(f"  {r['subj']} | {r['rel']} | {r['obj']} | {r['date']}")

nuri_ref_date = nuri_praise_kuwait[0]['date'] if nuri_praise_kuwait else None
all_praise_kuwait = [r for r in RECORDS if 'praise' in r['rel'].lower() and 'kuwait' in r['obj'].lower()]
print(f'\nAll praise kuwait: {len(all_praise_kuwait)}')
if nuri_ref_date:
    before = [r for r in all_praise_kuwait if r['date'] < nuri_ref_date]
    print(f'Before {nuri_ref_date}: {len(before)}')
    entities = sorted(set(r['subj'] for r in before if 'nuri' not in r['subj'].lower()))
    print(f'Entities: {entities}')

print()
# Q12: "Before 14 October 2015, who made Burundi suffer from conventional military forces?"
# Truth: ['Al-Shabaab', 'Military (Burundi)']
conv_burundi = [r for r in RECORDS if 'conventional military' in r['rel'].lower() and 'burundi' in r['obj'].lower() and r['date'] < '2015-10-14']
print(f'Conventional military vs Burundi before 2015-10-14: {len(conv_burundi)}')
for r in conv_burundi:
    print(f"  {r['subj']} | {r['rel']} | {r['obj']} | {r['date']}")
