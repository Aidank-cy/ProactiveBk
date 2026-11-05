#!/usr/bin/env python3
"""Run the bounded, resumable GitHub PR feasibility pilot."""
from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
from datetime import timedelta
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pr_feasibility.analysis import extract  # noqa: E402
from pr_feasibility.collect import collect_pr, normalize_events  # noqa: E402
from pr_feasibility.discovery import STRATA, discover_repositories, iso_date, merged_pr_frame, repository_order, sample_prs  # noqa: E402
from pr_feasibility.github_client import GitHubClient, github_token  # noqa: E402
from pr_feasibility.report import build_statistics, write_reports  # noqa: E402
from pr_feasibility.semantic import annotate_cutoff  # noqa: E402

LOG = logging.getLogger("pilot")


def jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))


def csvfile(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("")
        return
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with path.open("w", newline="") as out:
        writer = csv.DictWriter(out, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v
                             for k, v in row.items()})


def save_state(results, processed, repos, sampled, features, cutoffs, intents, frames):
    csvfile(results / "repositories.csv", repos)
    csvfile(results / "sampled_prs.csv", sampled)
    csvfile(results / "trajectory_features.csv", features)
    jsonl(results / "candidate_cutoffs.jsonl", cutoffs)
    jsonl(results / "candidate_intents.jsonl", intents)
    csvfile(results / "feasibility_labels.csv", [{"repository": f["repository"], "pr_number": f["pr_number"],
                                                    "url": f["url"], "provisional_label": f["provisional_label"],
                                                    "reason_codes": f["reason_codes"]} for f in features])
    csvfile(results / "manual_review_queue.csv", [{"pr_url": c["pr_url"], "repository": c["repository"],
                                                       "pr_number": c["pr_number"], "cutoff_timestamp": c["cutoff_timestamp"],
                                                       "commit_sha": c["commit_sha"], "earlier_context_preview": c["context_preview"],
                                                       "future_feedback_preview": c["future_preview"],
                                                       "later_revision_sha": c["later_revision_sha"],
                                                       "possible_later_revision_sha": c["possible_later_revision_sha"],
                                                       "provisional_label": next((f["provisional_label"] for f in features if f["repository"] == c["repository"] and f["pr_number"] == c["pr_number"]), ""),
                                                       "evidence_event_ids": c["supporting_event_ids"],
                                                       "feedback_source_url": c["future_source_url"],
                                                       "earlier_source_urls": c["earlier_source_urls"],
                                                       "commit_url": f"https://github.com/{c['repository']}/commit/{c['commit_sha']}",
                                                       "uncertainty_notes": c["leakage_note"] + "; " + ", ".join(c["rejection_reasons"]),
                                                       "human_grounding": "", "human_inferability": "", "human_relevance": "",
                                                       "human_label": "", "human_notes": ""} for c in cutoffs])
    processed.mkdir(parents=True, exist_ok=True)
    (processed / "pr_sampling_frames.json").write_text(json.dumps(frames, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=ROOT / "config.yaml")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--analysis-only", action="store_true", help="Rebuild derived outputs from saved raw PR responses without API calls")
    args = parser.parse_args()
    cfg = yaml.safe_load(args.config.read_text())
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    if args.analysis_only:
        return reanalyze(args.root.resolve(), cfg)
    if cfg.get("llm_provider", "none") != "none":
        LOG.warning("LLM assisted annotations remain unverified and are never used as ground truth")
    token = github_token(cfg.get("allow_gh_auth", True))
    if not token:
        LOG.error("No valid GITHUB_TOKEN or authenticated gh session. No empirical results generated.")
        return 2
    root = args.root.resolve()
    raw, processed, results, reports = [root / name for name in ("data/raw", "data/processed", "results", "reports")]
    client = GitHubClient(token, root / ".cache", cfg["request_timeout_seconds"],
                          cfg["request_retries"], cfg["rate_limit_floor"])
    try:
        client.get("/user", refresh=True)
    except Exception as exc:
        LOG.error("GitHub authentication check failed: %s. No empirical results generated.", exc)
        return 2
    start, end = iso_date(cfg["observation_start"]), iso_date(cfg.get("observation_end"))
    repo_path = processed / "repository_candidates.json"
    if repo_path.exists():
        repositories = json.loads(repo_path.read_text())
    else:
        repositories = discover_repositories(client, cfg)
        repo_path.parent.mkdir(parents=True, exist_ok=True)
        repo_path.write_text(json.dumps(repositories, indent=2))
    order = repository_order(repositories, cfg)
    sampled, frames = [], {}
    chosen_owners = set()
    for low, high in STRATA:
        label = f"{low}-{high or 'plus'}"
        candidates = order[label]
        selected_count = 0
        while selected_count < cfg["repositories_per_stratum"]:
            if not candidates:
                LOG.error("Stratum %s exhausted before target count", label)
                break
            # Distinct owner preference, still following the seeded shuffled order otherwise.
            idx = next((i for i, r in enumerate(candidates) if r["full_name"].split("/")[0] not in chosen_owners), 0)
            row = candidates.pop(idx)
            repo = row["full_name"]
            frame, shards = merged_pr_frame(client, repo, start, end)
            frames[repo] = {"shards": shards, "frame_count": len(frame),
                            "complete": all(s["complete"] for s in shards)}
            row["recent_merged_prs"] = sum(iso_date((item.get("closed_at") or "")[:10]) >= end - timedelta(days=cfg["recent_activity_days"])
                                            for item in frame if item.get("closed_at"))
            row["recent_pr_activity_status"] = "merged_prs_in_sample_frame_last_configured_days"
            if not frames[repo]["complete"]:
                row["replacement_reason"] = "INCOMPLETE_PR_SEARCH_FRAME"
                LOG.warning("Skipping %s: incomplete PR search frame", repo)
                continue
            records, problem = sample_prs(frame, cfg, repo, seed_offset=selected_count + (low * 100), client=client)
            if problem:
                row["replacement_reason"] = problem
                LOG.info("Replacing %s: %s", repo, problem)
                continue
            row["selected"] = True
            selected_count += 1
            chosen_owners.add(repo.split("/")[0])
            sampled.extend(records)
            save_state(results, processed, repositories, sampled, [], [], [], frames)
    features, cutoffs, intents = [], [], []
    consecutive_connection_errors = 0
    for record in sampled:
        repo, number = record["repository"], record["number"]
        LOG.info("collecting repository=%s pr=%s", repo, number)
        try:
            data = collect_pr(client, repo, number, raw, cfg)
            events = normalize_events(data)
            owner, name = repo.split("/")
            event_path = processed / "events" / owner / name / f"{number}.json"
            event_path.parent.mkdir(parents=True, exist_ok=True)
            event_path.write_text(json.dumps(events, ensure_ascii=False))
            feature, these_cutoffs, these_intents = extract(data, events, cfg)
            for cutoff in these_cutoffs:
                if cfg.get("llm_provider", "none") != "none":
                    try:
                        cutoff["llm_annotation"] = annotate_cutoff(cutoff, cfg)
                    except Exception as exc:
                        LOG.warning("llm_annotation_failed repository=%s pr=%s error=%s", repo, number, exc)
            feature["sampling_group"] = record["sampling_group"]
            features.append(feature)
            cutoffs.extend(these_cutoffs)
            intents.extend(these_intents)
            save_state(results, processed, repositories, sampled, features, cutoffs, intents, frames)
            consecutive_connection_errors = 0
        except Exception as exc:
            LOG.exception("collection_failed repository=%s pr=%s", repo, number)
            error_path = results / "errors.jsonl"
            with error_path.open("a") as output:
                output.write(json.dumps({"repository": repo, "pr_number": number, "error": str(exc)}) + "\n")
            if any(marker in str(exc) for marker in ("ProxyError", "ConnectionError", "Connection refused", "NameResolutionError")):
                consecutive_connection_errors += 1
                if consecutive_connection_errors >= 3:
                    LOG.error("Stopping after three consecutive connection failures; cached data and partial results remain resumable")
                    break
            else:
                consecutive_connection_errors = 0
    stats = build_statistics(repositories, sampled, features, cutoffs, frames)
    (results / "summary_statistics.json").write_text(json.dumps(stats, indent=2))
    done = {(f["repository"], f["pr_number"]) for f in features}
    unresolved = [{"repository": r["repository"], "pr_number": r["number"], "url": r["url"]}
                  for r in sampled if (r["repository"], r["number"]) not in done]
    csvfile(results / "unresolved_prs.csv", unresolved)
    (results / "collection_status.json").write_text(json.dumps({"sampled": len(sampled),
        "collected": len(features), "unresolved": len(unresolved),
        "complete": not unresolved}, indent=2))
    write_reports(reports, stats, repositories, sampled, features, cutoffs, raw, cfg)
    LOG.info("completed selected_repositories=%s sampled_prs=%s collected_prs=%s",
             sum(r["selected"] for r in repositories), len(sampled), len(features))
    return 0 if len(features) == len(sampled) and len(sampled) == 6 * (cfg["random_prs_per_repository"] + cfg["enriched_prs_per_repository"]) else 1


def reanalyze(root: Path, cfg: dict):
    raw, processed, results, reports = [root / name for name in ("data/raw", "data/processed", "results", "reports")]
    with (results / "repositories.csv").open() as file:
        repositories = list(csv.DictReader(file))
    for row in repositories:
        row["selected"] = row["selected"] == "True"
        for key in ("stars", "forks", "recent_merged_prs"):
            row[key] = int(row[key]) if row.get(key) else None
    with (results / "sampled_prs.csv").open() as file:
        sampled = list(csv.DictReader(file))
    for row in sampled:
        row["number"] = int(row["number"])
    frames = json.loads((processed / "pr_sampling_frames.json").read_text())
    features, cutoffs, intents = [], [], []
    for record in sampled:
        owner, repo = record["repository"].split("/")
        path = raw / owner / repo / f"{record['number']}.json"
        if not path.exists():
            LOG.warning("raw PR missing: %s", path)
            continue
        data = json.loads(path.read_text())
        events = normalize_events(data)
        event_path = processed / "events" / owner / repo / f"{record['number']}.json"
        event_path.parent.mkdir(parents=True, exist_ok=True)
        event_path.write_text(json.dumps(events, ensure_ascii=False))
        feature, these_cutoffs, these_intents = extract(data, events, cfg)
        feature["sampling_group"] = record["sampling_group"]
        features.append(feature)
        cutoffs.extend(these_cutoffs)
        intents.extend(these_intents)
    save_state(results, processed, repositories, sampled, features, cutoffs, intents, frames)
    stats = build_statistics(repositories, sampled, features, cutoffs, frames)
    (results / "summary_statistics.json").write_text(json.dumps(stats, indent=2))
    done = {(f["repository"], f["pr_number"]) for f in features}
    unresolved = [{"repository": r["repository"], "pr_number": r["number"], "url": r["url"]}
                  for r in sampled if (r["repository"], r["number"]) not in done]
    csvfile(results / "unresolved_prs.csv", unresolved)
    (results / "collection_status.json").write_text(json.dumps({"sampled": len(sampled),
        "collected": len(features), "unresolved": len(unresolved), "complete": not unresolved}, indent=2))
    write_reports(reports, stats, repositories, sampled, features, cutoffs, raw, cfg)
    LOG.info("offline_analysis_complete sampled=%s collected=%s cutoffs=%s", len(sampled), len(features), len(cutoffs))
    return 0 if not unresolved else 1


if __name__ == "__main__":
    raise SystemExit(main())
