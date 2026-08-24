import json
import re
from pathlib import Path

path = Path(r"C:\Users\sy271\.cursor\projects\c-Users-sy271-Downloads-RepairAgent-main-RepairAgent-main\agent-transcripts\4780827d-23ef-42e5-8b2c-8a706dcbf183\4780827d-23ef-42e5-8b2c-8a706dcbf183.jsonl")
lines = path.read_text(encoding="utf-8").splitlines()

def get_text(line_idx):
    obj = json.loads(lines[line_idx])
    content = obj.get("message", {}).get("content", [])
    if isinstance(content, str):
        return content
    parts = []
    for b in content:
        if isinstance(b, dict) and b.get("type") == "text":
            parts.append(b.get("text", ""))
    return "\n".join(parts)

# Dump line 7 full to file
l7 = get_text(6)
Path(r"c:\Users\sy271\Downloads\RepairAgent-main\RepairAgent-main\_line7_dump.txt").write_text(l7, encoding="utf-8")
print("line7 len", len(l7))

# search all lines for rows = [
for i, raw in enumerate(lines):
    obj = json.loads(raw)
    text = get_text(i) if False else ""
    try:
        content = obj.get("message", {}).get("content", [])
        text = "".join(b.get("text","") for b in content if isinstance(b, dict) and b.get("type")=="text")
    except:
        continue
    if "rows = [" in text:
        print("rows found on line", i+1, "len", len(text))

l14 = get_text(13)
Path(r"c:\Users\sy271\Downloads\RepairAgent-main\RepairAgent-main\_line14_dump.txt").write_text(l14, encoding="utf-8")
print("line14 len", len(l14))
