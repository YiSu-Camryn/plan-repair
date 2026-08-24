import json
import re
from pathlib import Path
path = Path(r"C:\Users\sy271\.cursor\projects\c-Users-sy271-Downloads-RepairAgent-main-RepairAgent-main\agent-transcripts\4780827d-23ef-42e5-8b2c-8a706dcbf183\4780827d-23ef-42e5-8b2c-8a706dcbf183.jsonl")
raw = path.read_text(encoding="utf-8")
for pat in ["rows = [", "rows=[", "rows =["]:
    if pat in raw:
        print("found", pat, raw.count(pat))

lines = raw.splitlines()
for i, line in enumerate(lines):
    if "rows" in line.lower() and "[" in line:
        print("line", i+1, "snippet", line[:200])

# parse line 14 code block
def get_text(i):
    obj = json.loads(lines[i])
    content = obj.get("message", {}).get("content", [])
    return "".join(b.get("text","") for b in content if isinstance(b, dict) and b.get("type")=="text")

text = get_text(13)
# extract code block after #7
m = re.search(r"```\s*\n(#7.*?)\n```", text, re.DOTALL)
if m:
    block = m.group(1)
    print("block lines", len(block.splitlines()))
    Path("_block.txt").write_text(block, encoding="utf-8")

# parse bugs from lines like #7   Time 14
bugs = []
for ln in text.splitlines():
    mm = re.match(r"^#(\d+)\s+([A-Za-z]+)\s+(\d+)\s", ln.strip())
    if mm:
        bugs.append(f"{mm.group(2)}-{int(mm.group(3))}")
print("from line14 markdown:", len(bugs), bugs)
