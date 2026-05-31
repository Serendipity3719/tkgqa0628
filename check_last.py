content = open('E:/RAG_Agent_Experiment/agent_v6.py', 'r', encoding='utf-8').read()
lines = content.split('\n')
print('\n'.join(f'{i+1500} | {l}' for i, l in enumerate(lines[1499:])))
