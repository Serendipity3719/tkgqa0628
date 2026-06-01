"""Revert FIX GG entirely - it's causing regressions."""
with open('agent_v9.py', 'r', encoding='utf-8') as f:
    content = f.read()

old = """        # FIX GG: "fighter" noise word in ref_kws
        # "Hizbul Islam fighter" → KB: "Combatant (Hizbul Islam)" — 'fighter' not in KB name
        # Only remove 'fighter/fighters' which never appear in KB entity names
        ref_kws_cur = facets['reference']['entity_keywords']
        if ref_kws_cur:
            NOISE_ROLE_WORDS = {'fighter', 'fighters'}
            filtered_ref = [kw for kw in ref_kws_cur if kw.lower() not in NOISE_ROLE_WORDS]
            if filtered_ref and len(filtered_ref) >= 1:
                facets['reference']['entity_keywords'] = filtered_ref"""

new = """        # FIX GG: removed - caused regressions
        # "fighter" removal was too aggressive for KB entity names like "Combatant (Hizbul Islam)"
        # The LLM should handle this via better prompting instead"""

if old in content:
    content = content.replace(old, new)
    with open('agent_v9.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('REVERTED OK')
else:
    print('NOT FOUND')
    idx = content.find('NOISE_ROLE_WORDS')
    if idx >= 0:
        print(repr(content[idx-100:idx+300]))
