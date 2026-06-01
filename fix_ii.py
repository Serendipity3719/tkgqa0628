"""Fix FIX II: receive visit direction."""
with open('agent_v9.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find the actual text in _detect_visit_direction
idx = content.find("'receive', 'received'")
if idx >= 0:
    print("Found at:", idx)
    print(repr(content[idx-200:idx+300]))
else:
    # Try another search
    idx2 = content.find('_detect_visit_direction')
    print(f"_detect_visit_direction at: {idx2}")
    if idx2 >= 0:
        print(repr(content[idx2:idx2+600]))
