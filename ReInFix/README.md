# ReInFix + RepairAgent Spec

ReInFix repair pipeline with the **same behavioral spec** (generate + verify) as `repair_agent/`.
RepairAgent batch jobs are unchanged; use this directory for the ReInFix backend only.

## Architecture

| Step | What | Status |
|------|------|--------|
| **1** | Local `src/spec/` (copied from RepairAgent) | Done |
| **2** | Thin adapter: dataset → `generate_spec` + bootstrap + verify | Done (see below) |
| **3** | Wire spec into Joern ReAct / patch prompts + baseline/spec mode switch | Done |

**Primary import (Step 2):**

```python
from spec_integration.spec_adapter import run_spec_for_dataset_bug
# or: from spec_adapter import run_spec_for_dataset_bug
```

## Step 2 — Spec adapter (verify before batch)

### What the adapter does

1. Read `D4J_dataset/defects4j-sf.json` (or `-mf.json`)
2. Build `localization_info` (dataset + GT + optional `defects4j info`)
3. Build `test_results` (live `defects4j test` or dataset errors)
4. Checkout → `auto_gpt_workspace/{project_lower}_{id}_buggy`
5. Symlink Joern path → `defects4j/{Project}-{id}_buggy`
6. Call local `spec.generate_spec` + verifier
7. Write logs under `experimental_setups/experiment_N/spec_logs/`

### Prerequisites

- `repair_agent/` sibling with full `defects4j/{buggy-lines,buggy-methods,framework}`
- Set `REPAIRAGENT_SRC` (or `REPAIRAGENT_ROOT`) if not at `../repair_agent`
- `OPENAI_API_KEY` (and `OPENAI_API_BASE_URL` for Bedrock)
- Shared venv: `repair_agent/venv` (recommended)

### Environment variables

| Variable | Default | Meaning |
|----------|---------|---------|
| `REPAIRAGENT_SRC` | `../repair_agent` | RepairAgent root (checkout + D4J assets) |
| `REINFIX_SPEC_RUN_TESTS` | `1` | Run `defects4j test` for `test_results` |
| `REINFIX_SPEC_USE_D4J_INFO` | `1` | Append `defects4j info` root cause to localization |
| `REINFIX_SPEC_RESTORE_AFTER_TEST` | `0` | Re-checkout after test (RepairAgent parity; slow) |
| `SPEC_SMOKE_MODEL` | `gpt-4o-mini` | Model for smoke test |

Config file: `hyperparams.json` → `spec_control.max_attempts` (default 3).

### Step 2 acceptance (run on cluster / machine with Defects4J)

```bash
cd ReInFix
export REPAIRAGENT_SRC=../repair_agent
export OPENAI_API_KEY=...

# 1) Environment check (no LLM)
python scripts/verify_spec_environment.py Chart-1

# 2) Live spec smoke test (one bug, needs API key)
python scripts/run_spec_smoke_test.py Chart-1

# Or both:
chmod +x scripts/run_step2_acceptance.sh
./scripts/run_step2_acceptance.sh Chart-1
```

**Pass criteria:**

- [ ] `verify_spec_environment.py` — all required checks green (api_key optional)
- [ ] `run_spec_smoke_test.py` — `success: true`, non-empty `prompt_section`
- [ ] `experimental_setups/experiment_N/spec_logs/` contains `spec_*` files
- [ ] Smoke summary shows `joern_link_ok: true`

### Faster smoke (skip live test / d4j info)

```bash
python scripts/run_spec_smoke_test.py Chart-1 --no-tests --no-d4j-info
```

## Pipeline mode switch (baseline vs spec)

Compare original ReInFix against ReInFix+spec with one flag. Both modes write the same
`bug_results.jsonl` schema; baseline records `spec_skipped: true` and `backend: reinfix`.

| Mode | Meaning | `backend` field |
|------|---------|-----------------|
| **baseline** | Original ReInFix: Joern ReAct → patch → validate (no spec) | `reinfix` |
| **spec** | Spec generate+verify → inject ReAct + patch → validate | `reinfix+spec` |

**Priority:** CLI `--mode` > `REINFIX_MODE` env > `hyperparams.pipeline_mode` > default `spec`.

```bash
# Baseline (original ReInFix)
./run_reinfix_baseline.sh bug_list/sf_sample.txt hyperparams.json deepseek.v3.2
# or:
REINFIX_MODE=baseline ./run_reinfix_batch.sh bug_list/sf_sample.txt hyperparams.json deepseek.v3.2

# ReInFix + spec (default)
./run_reinfix_spec.sh bug_list/sf_sample.txt hyperparams.json deepseek.v3.2
# or:
./run_reinfix_batch.sh bug_list/sf_sample.txt hyperparams.json deepseek.v3.2

# CLI override
python src/reinfix_pipeline.py bug_list/sf_sample.txt hyperparams.json gpt-4o-mini --mode baseline
python src/agent/react_sf_gen_patch.py --bug Chart-1 --mode baseline --model gpt-4o-mini
```

`hyperparams.json` may set `"pipeline_mode": "spec"` for reproducible experiments.

**Step 3 static acceptance (no LLM, no Joern):**

```bash
chmod +x scripts/run_step3_mode_acceptance.sh
./scripts/run_step3_mode_acceptance.sh Chart-1
```

## Step 3 — Spec injection (2 points)

Verified `prompt_section` from Step 2 is injected in **`spec_integration/spec_prompts.py`**:

| # | Stage | Function |
|---|--------|----------|
| 1 | Joern ReAct analysis | `build_react_prompt_template()` + `react_prompt_kwargs()` |
| 2 | Patch generation | `build_patch_generation_prompt()` |

Main runner: `src/reinfix_pipeline.py` (also via `src/agent/react_sf_gen_patch.py`).

### Step 3 check (no LLM, no Joern)

```bash
python scripts/verify_spec_injection.py Chart-1
```

After a full bug run, verified spec and rendered injection prompts are saved under  
`experimental_setups/experiment_N/spec_artifacts/`:

- `prompt_section_<bug>.txt` — verified spec from Step 2
- `react_prompt_<bug>.txt` — injection point 1 (ReAct)
- `patch_prompt_sample_<bug>.txt` — injection point 2 (patch template)

Quick check (no LLM):

```bash
chmod +x scripts/run_step3_acceptance.sh
./scripts/run_step3_acceptance.sh Chart-1
# or: python scripts/verify_spec_injection.py Chart-1
```

## Full pipeline (Step 3 — batch)

Per bug:

1. **Spec** — adapter → `generate_spec` + verifier → `prompt_section`
2. **Joern ReAct** — spec injected into analysis prompt (`spec_integration/spec_prompts.py`, injection point 1)
3. **Patch generation** — spec injected into patch prompt (injection point 2)
4. **Validation** — `sf_val_d4j.py` → plausible patch
5. Log — `experimental_setups/experiment_N/bug_results.jsonl`

Additional prerequisites for batch:

- **Joern** server running (`src/joern.sh` or cluster setup)
- **RAG** server: `python src/rag_search_server.py` (for `example_patch_search_tool`)

```bash
cd ReInFix
export REPAIRAGENT_SRC=../repair_agent
export OPENAI_API_KEY=...

chmod +x run_reinfix_batch.sh
./run_reinfix_batch.sh bug_list/sf_sample.txt hyperparams.json deepseek.v3.2

# Or from src/agent (same pipeline, Step 3 entry):
cd src/agent
python react_sf_gen_patch.py --bug Chart-1 --model gpt-4o-mini
python react_sf_gen_patch.py ../../bug_list/sf_sample.txt hyperparams.json gpt-4o-mini
```

Bug list format: `Chart-1` or `Chart 1` per line. Bugs must exist in `D4J_dataset/defects4j-sf.json`.

## Slurm (example)

Run Step 2 acceptance first on the login node or an interactive session, then batch:

```bash
sbatch examples/run_reinfix_batch.sbatch.example
```

## Results

```bash
EXP=experimental_setups/experiment_2
cat $EXP/bug_results.jsonl
python experimental_setups/summarize_experiment.py experiment_2
```

Summarize uses the same script as RepairAgent (compatible schema; includes `"backend": "reinfix+spec"`).

## Layout

| Path | Role |
|------|------|
| `src/spec/` | Local spec generate + verify (Step 1) |
| `src/spec_integration/spec_adapter.py` | **Thin adapter (Step 2 main API)** |
| `src/spec_integration/bootstrap.py` | Symlink D4J assets from RepairAgent |
| `src/spec_integration/verify.py` | Step 2 environment checks |
| `scripts/verify_spec_environment.py` | CLI for verify |
| `scripts/run_spec_smoke_test.py` | CLI for live spec smoke test |
| `scripts/run_step3_mode_acceptance.sh` | Step 3 mode + injection checks (no LLM) |
| `scripts/verify_pipeline_mode_wiring.py` | Step 3 pipeline branch check |
| `run_reinfix_baseline.sh` | Batch entry with `REINFIX_MODE=baseline` |
| `run_reinfix_spec.sh` | Batch entry with `REINFIX_MODE=spec` |
| `src/spec_integration/spec_prompts.py` | Step 3 spec injection (ReAct + patch prompts) |
| `src/reinfix_pipeline.py` | Full batch runner (spec → ReAct → patch) |
| `src/agent/react_sf_gen_patch.py` | Step 3 CLI entry (single bug or batch) |
| `src/spec_bridge.py` | Legacy wrapper (prefers adapter; falls back to RepairAgent autogpt) |
| `src/results_recorder.py` | `bug_results.jsonl` (uses RepairAgent metrics helpers) |
| `run_reinfix_batch.sh` | Shell entry |

Multi-function (`react_mf_gen_patch.py`) is not wired yet; use single-function dataset for spec runs.
