import json
from pathlib import Path
path = Path(r"C:\Users\sy271\.cursor\projects\c-Users-sy271-Downloads-RepairAgent-main-RepairAgent-main\agent-transcripts\4780827d-23ef-42e5-8b2c-8a706dcbf183\4780827d-23ef-42e5-8b2c-8a706dcbf183.jsonl")
lines = path.read_text(encoding="utf-8").splitlines()

# Full parse line 7
obj = json.loads(lines[6])
print(json.dumps(obj, ensure_ascii=False, indent=2)[:8000])
