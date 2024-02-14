import json

with open('distros.json', 'r', encoding='utf-8') as f:
    distros = json.load(f)
    print(len(distros))
