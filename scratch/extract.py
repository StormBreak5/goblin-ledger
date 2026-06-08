import re

js = open('scratch/index.js', encoding='utf-8').read()
matches = re.finditer(r'switch\([a-zA-Z0-9_.]+\(\d+\)\)\{', js)
for m in matches:
    start = m.start()
    end = start + 2000 # Grab 2000 chars after switch
    print("MATCH AT", start)
    print(js[start:end])
    print("="*80)
