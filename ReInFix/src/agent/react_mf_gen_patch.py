#!/usr/bin/env python3
"""Multi-function ReInFix entry — not wired to spec pipeline yet.

Use single-function pipeline instead:
  cd ReInFix && ./run_reinfix_batch.sh <bugs> hyperparams.json <model>
"""

from __future__ import annotations

import sys

if __name__ == "__main__":
    print(
        "react_mf_gen_patch.py: multi-function + spec is not implemented yet.\n"
        "Use: ./run_reinfix_batch.sh with bugs from D4J_dataset/defects4j-sf.json",
        file=sys.stderr,
    )
    sys.exit(2)
