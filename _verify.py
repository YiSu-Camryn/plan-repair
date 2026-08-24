import json
from pathlib import Path

path = Path(r"C:\Users\sy271\.cursor\projects\c-Users-sy271-Downloads-RepairAgent-main-RepairAgent-main\agent-transcripts\4780827d-23ef-42e5-8b2c-8a706dcbf183\4780827d-23ef-42e5-8b2c-8a706dcbf183.jsonl")

def get_text(line_obj):
    msg = line_obj.get("message") or line_obj
    content = msg.get("content") if isinstance(msg, dict) else None
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "\n".join(parts)
    return content or ""

lines = path.read_text(encoding="utf-8").splitlines()
for li in [52]:
    obj = json.loads(lines[li])
    text = get_text(obj)
    spec_true = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                e = json.loads(line)
            except:
                continue
            if e.get("spec_success") is True:
                spec_true.append((e.get("project"), e.get("bug_index"), e.get("spec_final_verdict"), e.get("repair_ran")))
    print("spec_success true count:", len(spec_true))
    for x in spec_true:
        print(x)

# find all user lines with bug_results.jsonl
for i, raw in enumerate(lines):
    obj = json.loads(raw)
    if obj.get("role") != "user":
        continue
    text = get_text(obj)
    if "bug_results.jsonl" in text or '"spec_success"' in text:
        cnt = sum(1 for ln in text.splitlines() if ln.strip().startswith("{") and "project" in ln)
        print(f"user line {i+1}: ~{cnt} json lines, has bug_results:", "bug_results.jsonl" in text)
