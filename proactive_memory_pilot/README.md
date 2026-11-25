# Controlled Proactive vs Memory Pilot

This directory contains the evaluation framework, a toy fixture, and four fixed scenarios reconstructed from the local VibeLifeBench source data. The reconstructed scenarios include explicitly audited experimental supplements; they are not verbatim VibeLifeBench tasks.

## Fixed four-scenario pilot data

The formal data lives in [evaluation/data/scenarios](evaluation/data/scenarios). `rental.json`, `travel.json`, `shopping.json`, and `team_building.json` each contain one complete scenario. `all_scenarios.json` combines the four and is generated from the same builder. [Dataset summary](evaluation/data/scenarios/documentation/dataset_summary.md) gives per-scenario event, question, opportunity, and API-call counts. Each reconstruction document records the complete story, source record and original-event mapping, controlled additions, fixed tasks, every Stage's Ready set, its derived readiness matrix, and unresolved questions.

The four scenarios have 19 fixed tasks, 77 incremental events and 81 stages. With one model and one sample, a full run requires 2,616 requests: 2,205 Memory, 330 Reactive Single, and 81 Proactive. Initial-context token counts in the summary are UTF-8 estimates, not provider measurements. Data should be reviewed and frozen before a scored inference run, especially the controlled additions and the travel hotel inventory versus later receipt inconsistency.

To regenerate and check the data:

```bash
python -m evaluation.data.scenarios.materialize
python -m evaluation.data.scenarios.materialize --check
python -m pytest -q evaluation/tests
```

The dataset loader enforces both directions of `Ready iff all necessary conditions are Satisfied`, complete condition states, full required Memory question coverage for active tasks, transition labels, and chronological stages. Formal-data tests also validate the JSON Schema, original source paths, future-event isolation and equal Context Hashes. No model output modifies a later stage.

### Run with the direct API backend

The CLI's existing default backend remains `harness` for compatibility with the original pilot. For this four-scenario study, use `--backend direct`; it sends one stateless Chat Completions request per evaluation via the existing model config and does not start OpenClaw. The API key stays in the local `models.json` or the configured environment variable and is not written to results. `seed` is unsupported and rejected. `top_p` is sent only when configured. API usage fields stay null if the provider omits them. A prior single synthetic direct API connectivity smoke test is described below; the four formal scenarios have not been sent to a live API.

```bash
cd /home/hezd/nfs_hzd/ProactiveBk/proactive_memory_pilot
python -m evaluation.runner --config evaluation/configs/deepseek.yaml --dataset evaluation/data/scenarios/all_scenarios.json --mode all --backend direct --dry-run > /tmp/proactive_pilot_inputs.jsonl
python -m evaluation.runner --config evaluation/configs/deepseek.yaml --dataset evaluation/data/scenarios/all_scenarios.json --mode all --backend direct --output outputs/raw_results/four_scenarios.jsonl
python -m evaluation.review --results outputs/raw_results/four_scenarios.jsonl --dataset evaluation/data/scenarios/all_scenarios.json --output outputs/human_annotations/four_scenarios.jsonl
python -m evaluation.metrics --results outputs/raw_results/four_scenarios.jsonl --annotations outputs/human_annotations/four_scenarios.jsonl --dataset evaluation/data/scenarios/all_scenarios.json
python -m evaluation.failure_analysis --results outputs/raw_results/four_scenarios.jsonl --annotations outputs/human_annotations/four_scenarios.jsonl --dataset evaluation/data/scenarios/all_scenarios.json
```

Use `--scenario rental --stage s04` for a small dry run. Add later official data by editing the fixed builder, recording every source and supplement, regenerating the JSON and audit files, then running the same tests before inference. The separate JSONs, task registry, matching guidelines, and truth labels must be frozen together; do not modify labels in response to a model's predictions.

## Harness reuse

VibeLifeBench's entry point is `VibeLifeBench/scripts/run_eval.py`. It generates a Terrarium trial config; the pinned Terrarium commit is `7d641ea587687e7360f2bf74951b9353c2894b18`. The default agent is `terrarium.agent.openclaw.OpenClawAgent`, running OpenClaw in a Terrarium Docker workspace. Its `setup()` writes model config and a system prompt override; `act()` sends one instruction using a session UUID and reads the session JSONL for response and usage. VibeLifeBench's normal timeline tasks, MCP mock services, and rubrics are intentionally not invoked here.

`evaluation/harness/adapter.py` constructs the **same OpenClawAgent**, creates a fresh Terrarium workspace per request, calls `setup()` and one `act()`, then destroys the workspace. It supplies the existing `models.json` format, a common system prompt, and no MCP servers. The adapter sets OpenClaw's tool deny list to `*` and requests compaction `off`; it rejects any visible tool call. It never directly calls the model API. The model key is read at runtime from the existing `models.json` or an environment variable named by `api_key_env`; neither the key nor the model config is written to experiment results. A real run still needs the `terrarium/openclaw` Docker image.

The default layout expects a sibling `VibeLifeBench/` directory next to `proactive_memory_pilot/`. Set `VIBELIFE_ROOT` and `models_config_path` if using another layout. The local `models.json` is not included in this repository.

OpenClaw's effective wire messages and parameter acceptance have **not yet been observed in a live smoke test**. OpenClaw may add its own hidden system content. The stored `input_messages` are the adapter's requested messages, not a captured provider HTTP payload. `systemPromptOverride`, `tools.deny`, and `compaction.mode=off` must be verified against the installed image before treating live results as fully controlled. The default harness also normally enables `exec`; this adapter's isolated workspace and deny config are essential controls. `max_output_tokens` is applied to OpenClaw's model `maxTokens`; temperature and top-p are passed as model params. Their effective provider values are unverified. Seed is rejected. The context-window preflight conservatively compares UTF-8 byte length plus output budget and overhead to the configured window; it cannot detect a provider-side smaller window or hidden truncation. If any of these controls are unsupported at runtime, discard the affected inference, document the behavior, and do not report a controlled Proactive Gap.

## Data contract

See [schema.json](evaluation/data/schema.json). A scenario has `initial_context`, ordered `events`, hidden `task_registry`, and one `evaluations` stage before events plus one after each event. Each stage includes hidden `ready_tasks`, `newly_ready_tasks`, `invalidated_tasks`, and per-task condition states (`Satisfied`, `Unsatisfied`, `Unknown`). Memory questions have `question_id`, `question`, `task_ids`, and hidden `ground_truth_answer`. `required_memory_facts` in each task refers to question IDs that must exist at each stage for a Task Memory result; otherwise it is Missing. Add formal data as JSON with this shape. The loader accepts either one scenario, a list, or `{"scenarios":[...]}`. The only supplied data, [synthetic_fixture.json](evaluation/data/synthetic_fixture.json), uses toy colored tokens to test code paths.

The context builder serializes only initial records and events through the current stage, preserving record order, IDs, timestamps, sources, and contents. `simulated_now` comes from the last visible record. All groups use exactly this context and the same system prompt. The last user query is the only group difference. Every call has an independent container, session, and single turn. Model output never feeds the next stage. No task is executed.

## Run

Use the Python environment already installed for VibeLifeBench:

```bash
cd /home/hezd/nfs_hzd/ProactiveBk/proactive_memory_pilot
PY=/home/hezd/nfs_hzd/ProactiveBk/VibeLifeBench/.venv/bin/python
$PY -m evaluation.runner --config evaluation/configs/deepseek.yaml --dataset evaluation/data/synthetic_fixture.json --mode all --stage s1 --dry-run
$PY -m evaluation.runner --config evaluation/configs/deepseek.yaml --dataset PATH_TO_FORMAL_DATA.json --mode all --output outputs/raw_results/run.jsonl
$PY -m evaluation.runner --config evaluation/configs/deepseek.yaml --dataset PATH_TO_FORMAL_DATA.json --mode all --output outputs/raw_results/run.jsonl --resume
$PY -m evaluation.review --results outputs/raw_results/run.jsonl --dataset PATH_TO_FORMAL_DATA.json --output outputs/human_annotations/run.jsonl
$PY -m evaluation.metrics --results outputs/raw_results/run.jsonl --annotations outputs/human_annotations/run.jsonl --dataset PATH_TO_FORMAL_DATA.json
$PY -m evaluation.failure_analysis --results outputs/raw_results/run.jsonl --annotations outputs/human_annotations/run.jsonl --dataset PATH_TO_FORMAL_DATA.json
$PY -m pytest -q evaluation/tests
```

Options: `--mode memory|reactive|proactive|reactive_batch|all`, `--scenario`, `--stage`, `--resume`, `--dry-run`. YAML config supports `models`, `models_config_path`, optional `api_key_env`, `api_base_url`, `temperature`, `top_p`, `max_output_tokens`, `timeout`, `retry`, `concurrency`, `num_samples`. All groups use the same config. Retry applies only to API errors; malformed JSON is recorded without a repair call. Resume skips successful and parsing-failure calls and retries API failures. The config sidecar excludes key sources.

## Inputs and outputs

For toy stage `s1`, all groups receive the same system prompt and serialized `{"simulated_now":"2026-01-02T00:00:00Z","records":[...]}`. Their final query differs:

```text
Memory:   Is token 1 authorized?
Reactive: Only evaluate the following task: Place blue token in box A.
Proactive: Identify all actionable user tasks from the provided context.
```

Valid response examples:

```json
{"answer":"yes","evidence":["e1"]}
{"actionable_tasks":[{"description":"Place blue token in box A.","evidence":["h0","e1"]}]}
{"actionable_tasks":[]}
```

One JSONL inference row stores run/model/harness IDs, scenario/stage/group/question/task/sample IDs, context hash, requested messages and prompt, raw/parsed response, usage or null, latency, status, error, and prompt version. `task_id` is null for Proactive. Status is `ok`, `api_error`, or `parsing_failure`; semantic correctness appears only in annotations and reports.

`review.py` emits blinded records with opaque `call_id`, model output, hidden truth and matching guidelines for the human reviewer. Fill `correct` for Memory. For each Reactive or Proactive prediction, fill `matched_task_id`, `match_status` (`Correct Match`, `Not Ready`, `Duplicate`, `Out of Scope`, `Unsupported Task`, `Needs Review`), `evidence_correct`, and `comment`. Unresolved `Needs Review` cases and missing labels are excluded from scoring pending one consistent revised truth set. A task can receive one Correct Match per call; duplicates are separate false positives. Keep the raw inference file unchanged while annotating.

`metrics.py` uses only the raw results, completed human annotations, and dataset truth. Undefined ratios are JSON `null`, with counts retained. It reports Memory question/task accuracy, Reactive confusion and rates, Proactive micro and per-scenario rates, empty-stage accuracy, duplicates, newly-ready recall, and both Proactive Gap denominators. `failure_analysis.py` exports all ready-task M/R/P combinations, core cases with complete requests and ground truth, and false positive predictions. Categories are descriptive, not causal conclusions.

## Current verification

Mock tests cover zero/one/multiple Ready tasks, invalidation, core M=1/R=1/P=0 gap, false positives, duplicates, API and JSON failures, missing annotation, zero denominators, future-event rejection, and parameter mismatch. Expected mock all-ready gap is `1/3`, newly-ready gap `1/2`; both are asserted.

A separate [direct API smoke test](evaluation/data/direct_api_smoke.json) was run at the user's request, without Terrarium or OpenClaw. One synthetic Proactive request to the configured `deepseek-flash` endpoint returned HTTP 200, valid JSON, 321 prompt tokens, 120 completion tokens, and 1.55 seconds latency. It is a connectivity test only; the model combined the two toy actions into one description, so no task score was assigned. A Harness smoke test remains unrun because the required OpenClaw Docker image is absent.
