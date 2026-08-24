import json
from pathlib import Path
path = Path(r"C:\Users\sy271\.cursor\projects\c-Users-sy271-Downloads-RepairAgent-main-RepairAgent-main\agent-transcripts\4780827d-23ef-42e5-8b2c-8a706dcbf183\4780827d-23ef-42e5-8b2c-8a706dcbf183.jsonl")
lines = path.read_text(encoding="utf-8").splitlines()

def get_text(i):
    obj = json.loads(lines[i])
    content = obj.get("message", {}).get("content", [])
    return "".join(b.get("text","") for b in content if isinstance(b, dict) and b.get("type")=="text")

for i in range(len(lines)):
    text = get_text(i)
    if "rows = [" in text:
        print("rows line", i+1)
    if "Time 14" in text and "#7" in text:
        print("time14 block line", i+1, "len", len(text))
    if "#7   Time 14" in text or "#7  Time 14" in text:
        print("exact marker line", i+1)
