import json
import re
from pathlib import Path

transcript = Path(
    r"C:\Users\sy271\.cursor\projects\c-Users-sy271-Downloads-RepairAgent-main-RepairAgent-main\agent-transcripts\099b7139-86b5-467a-8203-58093be39ee7\099b7139-86b5-467a-8203-58093be39ee7.jsonl"
)
batch_file = Path(
    r"c:\Users\sy271\Downloads\RepairAgent-main\RepairAgent-main\repair_agent\experimental_setups\batches\0"
)
out_file = Path(
    r"c:\Users\sy271\Downloads\RepairAgent-main\RepairAgent-main\spec_passed_out.txt"
)

spec_passed = {}

with transcript.open(encoding="utf-8") as f:
    for line in f:
        obj = json.loads(line)
        for item in obj.get("message", {}).get("content", []):
            if item.get("type") != "text":
                continue
            text = item.get("text", "")
            pattern = (
                r'\{"project": "([^"]+)", "bug_index": "([^"]+)".*?"spec_success": (true|false)'
            )
            for m in re.finditer(pattern, text, re.DOTALL):
                project, bug, success = m.group(1), m.group(2), m.group(3)
                if success == "true":
                    spec_passed[(project, bug)] = True

batch0 = []
with batch_file.open() as f:
    for line in f:
        line = line.strip()
        if line:
            p, b = line.split()
            batch0.append((p, b))

result = [f"{p} {b}" for p, b in batch0 if (p, b) in spec_passed]
output = f"COUNT={len(result)}\n" + ", ".join(result)
out_file.write_text(output, encoding="utf-8")
