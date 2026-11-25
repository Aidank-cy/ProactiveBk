"""Inference only; labels are never supplied to the harness."""
import argparse
import concurrent.futures
import json
import os
import time
import uuid
from pathlib import Path
import yaml

from .context_builder import build_context, canonical
from .dataset_loader import load_dataset
from .integrity import SYSTEM_PROMPT, check_pair, check_request
from .harness.adapter import invoke
from .direct_api import invoke as invoke_direct

ROOT = Path(__file__).resolve().parent
MEMORY = (ROOT / "prompts/memory.txt").read_text().strip()
READINESS = (ROOT / "prompts/task_readiness.txt").read_text().strip()
PROMPT_VERSION = "pilot-v1"


def make_request(scenario, stage, context, context_hash, kind, sample_id, model_name, question=None, task=None):
    if kind == "memory":
        suffix = f"{MEMORY}\n\nQuestion:\n{question['question']}"
    elif kind == "reactive":
        suffix = f"{READINESS}\n\nEvaluation scope:\nOnly evaluate the following task:\n{task['description']}"
    elif kind == "reactive_batch":
        suffix = READINESS + "\n\nEvaluation scope:\nOnly evaluate these tasks:\n" + "\n".join(
            f"- {t['description']}" for t in scenario["task_registry"])
    else:
        suffix = READINESS + "\n\nEvaluation scope:\nIdentify all actionable user tasks from the provided context."
    prompt = "Historical context and current environment state:\n" + canonical(context) + "\n\n" + suffix
    return {"model_name": model_name, "scenario_id": scenario["scenario_id"],
            "stage_id": stage["stage_id"], "evaluation_type": kind,
            "question_id": question["question_id"] if question else None,
            "task_id": task["task_id"] if task else None, "sample_id": sample_id,
            "context_hash": context_hash, "shared_context": context,
            "input_messages": [{"role": "system", "content": SYSTEM_PROMPT},
                               {"role": "user", "content": prompt}], "input_prompt": prompt,
            "prompt_version": PROMPT_VERSION}


def parse_response(raw, kind):
    value = json.loads(raw)
    if kind == "memory":
        if not isinstance(value, dict) or not isinstance(value.get("answer"), str) or not isinstance(value.get("evidence"), list):
            raise ValueError("invalid memory schema")
    elif not isinstance(value, dict) or not isinstance(value.get("actionable_tasks"), list) or any(
            not isinstance(t, dict) or not isinstance(t.get("description"), str) or not isinstance(t.get("evidence"), list)
            for t in value["actionable_tasks"]):
        raise ValueError("invalid task schema")
    return value


def execute(req, config, adapter=invoke):
    row = {**req, "run_id": config["run_id"], "model_parameters": config["model_parameters"],
           "harness_version": None, "raw_response": None, "parsed_response": None,
           "input_tokens": None, "output_tokens": None, "latency": None,
           "status": "api_error", "error_message": None}
    start = time.monotonic()
    for attempt in range(config.get("retry", 0) + 1):
        try:
            response = adapter(req, config)
            row.update(response)
            try:
                row["parsed_response"] = parse_response(response["raw_response"], req["evaluation_type"])
                row["status"] = "ok"
            except (ValueError, json.JSONDecodeError) as exc:
                row["status"] = "parsing_failure"
                row["error_message"] = str(exc)
            break
        except Exception as exc:
            message = str(exc)
            try:
                model_data = json.loads(Path(config["models_config_path"]).read_text())
                for provider in model_data.get("providers", {}).values():
                    secret = provider.get("apiKey")
                    if secret:
                        message = message.replace(secret, "[REDACTED]")
                env_name = config.get("api_key_env")
                if env_name and os.environ.get(env_name):
                    message = message.replace(os.environ[env_name], "[REDACTED]")
            except Exception:
                pass
            row["error_message"] = f"{type(exc).__name__}: {message[:300]}"
            if attempt == config.get("retry", 0):
                break
    row["latency"] = round(time.monotonic() - start, 4)
    return row


def requests_for(scenarios, config, mode="all", scenario_filter=None, stage_filter=None):
    modes = {"memory", "reactive", "proactive"} if mode == "all" else {mode}
    for s in scenarios:
        if scenario_filter and s["scenario_id"] != scenario_filter:
            continue
        tasks = {t["task_id"]: t for t in s["task_registry"]}
        for stage in s["evaluations"]:
            if stage_filter and stage["stage_id"] != stage_filter:
                continue
            context, context_hash = build_context(s, stage)
            for model_name in config["models"]:
                for sample_id in range(config.get("num_samples", 1)):
                    if "memory" in modes:
                        for q in stage["memory_questions"]:
                            req = make_request(s, stage, context, context_hash, "memory", sample_id, model_name, question=q)
                            check_request(req, s, stage)
                            yield req
                    if "reactive" in modes:
                        for task_id in stage["reactive_questions"]:
                            req = make_request(s, stage, context, context_hash, "reactive", sample_id, model_name, task=tasks[task_id])
                            check_request(req, s, stage)
                            yield req
                    if "reactive_batch" in modes:
                        req = make_request(s, stage, context, context_hash, "reactive_batch", sample_id, model_name)
                        check_request(req, s, stage)
                        yield req
                    if "proactive" in modes:
                        req = make_request(s, stage, context, context_hash, "proactive", sample_id, model_name)
                        check_request(req, s, stage)
                        yield req


def run(config_path, dataset_path, mode="all", output=None, dry_run=False, scenario=None, stage=None, resume=False, adapter=invoke, backend="harness"):
    config = yaml.safe_load(Path(config_path).read_text())
    if backend not in ("harness", "direct"):
        raise ValueError("backend must be harness or direct")
    if adapter is invoke and backend == "direct":
        adapter = invoke_direct
    config["models"] = config.get("models") or [config["model_name"]]
    if config.get("seed") is not None:
        raise ValueError("seed unsupported by selected adapter")
    config["model_parameters"] = {k: config.get(k) for k in ("temperature", "top_p", "max_output_tokens", "seed")}
    scenarios = load_dataset(dataset_path)
    requests = list(requests_for(scenarios, config, mode, scenario, stage))
    check_pair([{**r, "model_parameters": config["model_parameters"]} for r in requests])
    if not dry_run and adapter in (invoke, invoke_direct):
        models_data = json.loads(Path(config["models_config_path"]).read_text())
        for req in requests:
            provider, model_id = req["model_name"].split("/", 1)
            model = next(m for m in models_data["providers"][provider]["models"] if m["id"] == model_id)
            window = model.get("contextWindow")
            if not window:
                raise ValueError("model context window is unknown")
            # Byte count is a conservative ceiling for byte-based tokenizers; reserve overhead.
            if len(req["input_prompt"].encode()) + config.get("max_output_tokens", 0) + 4096 > window:
                raise ValueError("request may exceed model context window; refusing possible truncation")
    if dry_run:
        return requests
    output = Path(output or "outputs/raw_results/run.jsonl")
    output.parent.mkdir(parents=True, exist_ok=True)
    existing = [json.loads(line) for line in output.read_text().splitlines()] if resume and output.exists() else []
    config["run_id"] = existing[0]["run_id"] if existing else str(uuid.uuid4())
    key = lambda r: (r["model_name"], r["scenario_id"], r["stage_id"], r["evaluation_type"], r["question_id"], r["task_id"], r["sample_id"])
    requested = {key(r): r for r in requests}
    for old in existing:
        current = requested.get(key(old))
        if current is None or old["context_hash"] != current["context_hash"] or old["input_prompt"] != current["input_prompt"] or old["prompt_version"] != PROMPT_VERSION:
            raise ValueError("resume file contains a different dataset, prompt, or selection")
    done = {key(r) for r in existing if r["status"] in ("ok", "parsing_failure")}
    pending = [r for r in requests if key(r) not in done]
    safe_config = {k: v for k, v in config.items() if k not in ("api_key_env", "models_config_path")}
    sidecar = output.with_suffix(".config.json")
    if resume and sidecar.exists():
        previous = json.loads(sidecar.read_text())
        if previous != safe_config:
            raise ValueError("resume config differs from checkpoint")
    sidecar.write_text(json.dumps(safe_config, indent=2))
    rows = list(existing)
    with output.open("a" if resume else "w") as stream, concurrent.futures.ThreadPoolExecutor(max_workers=config.get("concurrency", 1)) as pool:
        futures = [pool.submit(execute, req, {**config, "model_name": req["model_name"]}, adapter) for req in pending]
        for future in concurrent.futures.as_completed(futures):
            row = future.result()
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
            stream.flush()
            rows.append(row)
    return rows


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--config", required=True)
    p.add_argument("--dataset", required=True)
    p.add_argument("--mode", choices=["all", "memory", "reactive", "proactive", "reactive_batch"], default="all")
    p.add_argument("--output")
    p.add_argument("--scenario")
    p.add_argument("--stage")
    p.add_argument("--resume", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--backend", choices=["harness", "direct"], default="harness")
    a = p.parse_args()
    rows = run(a.config, a.dataset, a.mode, a.output, a.dry_run, a.scenario, a.stage, a.resume, backend=a.backend)
    if a.dry_run:
        for row in rows:
            print(json.dumps(row, ensure_ascii=False))
    else:
        print(f"Saved {len(rows)} results")


if __name__ == "__main__":
    main()
