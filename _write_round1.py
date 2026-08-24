import json
import re
from pathlib import Path

transcript = Path(r"C:\Users\sy271\.cursor\projects\c-Users-sy271-Downloads-RepairAgent-main-RepairAgent-main\agent-transcripts\4780827d-23ef-42e5-8b2c-8a706dcbf183\4780827d-23ef-42e5-8b2c-8a706dcbf183.jsonl")
lines = transcript.read_text(encoding="utf-8").splitlines()

def get_text(i):
    obj = json.loads(lines[i])
    content = obj.get("message", {}).get("content", [])
    return "".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")

# Line 14 markdown block
text14 = get_text(13)
m = re.search(r"```\s*\n(#7.*?)\n```", text14, re.DOTALL)
block = m.group(1)
bugs14 = []
for ln in block.splitlines():
    mm = re.match(r"^#\d+\s+([A-Za-z]+)\s+(\d+)", ln.strip())
    if mm:
        bugs14.append(f"{mm.group(1)}-{int(mm.group(2))}")

# Line 7 rows from shell command embedded in tool_use
obj7 = json.loads(lines[6])
cmd = ""
for b in obj7["message"]["content"]:
    if b.get("type") == "tool_use" and b.get("name") == "Shell":
        cmd = b.get("input", {}).get("command", "")
        break
rows_match = re.search(r"rows = \[(.*?)\]", cmd, re.DOTALL)
rows_body = rows_match.group(1)
bugs7 = []
for tup in re.findall(r"\('([^']+)','([^']+)','[^']+'\)", rows_body):
    bugs7.append(f"{tup[0]}-{int(tup[1])}")

assert len(bugs14) == 35 and len(bugs7) == 35, (len(bugs14), len(bugs7))
assert bugs14 == bugs7, list(zip(bugs14, bugs7))

out = Path(r"c:\Users\sy271\Downloads\RepairAgent-main\RepairAgent-main\_round1.txt")
out.write_text(", ".join(bugs14) + "\n", encoding="utf-8")
print("OK", len(bugs14))
print(", ".join(bugs14))
