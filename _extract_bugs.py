import json
import re
from pathlib import Path

path = Path(r"C:\Users\sy271\.cursor\projects\c-Users-sy271-Downloads-RepairAgent-main-RepairAgent-main\agent-transcripts\4780827d-23ef-42e5-8b2c-8a706dcbf183\4780827d-23ef-42e5-8b2c-8a706dcbf183.jsonl")

def get_text(line_obj):
    msg = line_obj.get("message") or line_obj
    content = msg.get("content") if isinstance(msg, dict) else None
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "\n".join(parts)
    return ""

def extract_json_objects(text):
    entries = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return entries

def spec_passed(entry):
    if entry.get("repair_ran") is True:
        return True
    if entry.get("spec_success") is True:
        verdict = entry.get("spec_final_verdict")
        if verdict == "ACCEPT":
            return True
    return False

def bug_key(entry):
    proj = entry.get("project") or entry.get("Project")
    idx = entry.get("bug_index") or entry.get("bugIndex") or entry.get("index")
    if proj is not None and idx is not None:
        return f"{proj}-{int(idx)}" if str(idx).isdigit() else f"{proj}-{idx}"
    bid = entry.get("bug_id") or entry.get("bugId")
    if bid:
        return str(bid)
    return None

def sort_key(name):
    m = re.match(r"^([A-Za-z]+)-(\d+)$", name)
    if m:
        return (m.group(1).lower(), int(m.group(2)))
    return (name.lower(), 0)

lines = path.read_text(encoding="utf-8").splitlines()
print("num transcript lines", len(lines))

target_line_indices = [0, 52]
all_passed = set()

for li in target_line_indices:
    obj = json.loads(lines[li])
    text = get_text(obj)
    entries = extract_json_objects(text)
    passed_here = []
    for e in entries:
        if spec_passed(e):
            k = bug_key(e)
            if k:
                all_passed.add(k)
                passed_here.append(k)
    print(f"Line {li+1}: {len(entries)} json entries, {len(passed_here)} passed this round")

sorted_bugs = sorted(all_passed, key=sort_key)
out = Path(r"c:\Users\sy271\Downloads\RepairAgent-main\RepairAgent-main\_extract_out.txt")
with open(out, "w", encoding="utf-8") as f:
    f.write(str(len(sorted_bugs)) + "\n")
    f.write(", ".join(sorted_bugs) + "\n")
print("TOTAL", len(sorted_bugs))
print(",".join(sorted_bugs))
