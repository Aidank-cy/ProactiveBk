import json
import random
import sqlite3
from pathlib import Path

import pandas as pd


def select_repositories(cfg, root):
    inventory = (root / cfg["candidate_inventory"]).resolve()
    frame = pd.read_csv(inventory)
    if "processing_track" not in frame.columns:
        raise ValueError("Candidate inventory lacks processing_track")
    eligible = frame[frame.processing_track.eq("license_verified")].copy()
    restricted = frame[frame.processing_track.eq("license_unverified")].copy()
    if len(eligible) < cfg["repository_count"]:
        raise ValueError("Not enough license-verified repositories")
    checkpoint = (root / cfg["discovery_checkpoint"]).resolve()
    if checkpoint.exists():
        db = sqlite3.connect(checkpoint)
        pushed = {rid: json.loads(data).get("pushed_at") for rid, data in db.execute("SELECT id,data FROM repositories")}
        db.close()
        eligible["pushed_at"] = eligible.repository_id.map(pushed)
    else:
        eligible["pushed_at"] = None
    eligible["owner"] = eligible.full_name.str.split("/").str[0]
    eligible["created_day"] = pd.to_datetime(eligible.created_at, utc=True).map(lambda d: d.timestamp())
    eligible["activity_day"] = pd.to_datetime(eligible.pushed_at, utc=True, errors="coerce").map(lambda d: d.timestamp() if pd.notna(d) else 0)
    for source, target in (("stars", "star_bin"), ("total_pull_requests", "pr_bin"), ("total_issues", "issue_bin"), ("created_day", "age_bin"), ("activity_day", "activity_bin")):
        median = eligible[source].median()
        eligible[target] = (eligible[source] >= median).astype(int)
    seed = cfg["seed"]
    rng = random.Random(seed)
    candidates = eligible.to_dict("records")
    selected, used_ids, used_owners = [], set(), set()
    targets = [(s, p, a) for s in (0, 1) for p in (0, 1) for a in (0, 1)]
    rng.shuffle(targets)
    for s, p, a in targets[:cfg["repository_count"]]:
        pool = [r for r in candidates if r["repository_id"] not in used_ids]
        # Prefer exact star/PR/age stratum; issue and activity balance break ties.
        distances = [abs(r["star_bin"] - s) + abs(r["pr_bin"] - p) + abs(r["age_bin"] - a) for r in pool]
        minimum = min(distances)
        pool = [r for r, d in zip(pool, distances) if d == minimum]
        if any(r["owner"] not in used_owners for r in pool):
            pool = [r for r in pool if r["owner"] not in used_owners]
        issue_counts = {v: sum(x["issue_bin"] == v for x in selected) for v in (0, 1)}
        activity_counts = {v: sum(x["activity_bin"] == v for x in selected) for v in (0, 1)}
        best = min(issue_counts[r["issue_bin"]] + activity_counts[r["activity_bin"]] for r in pool)
        pool = [r for r in pool if issue_counts[r["issue_bin"]] + activity_counts[r["activity_bin"]] == best]
        choice = rng.choice(sorted(pool, key=lambda r: r["repository_id"]))
        choice["target_stratum"] = f"stars{s}_prs{p}_age{a}"
        choice["actual_stratum"] = f"stars{choice['star_bin']}_prs{choice['pr_bin']}_age{choice['age_bin']}"
        choice["replacement_reason"] = "empty_target_stratum" if minimum else ""
        choice["selection_method"] = "deterministic_stratified_balanced_random"
        choice["selection_seed"] = seed
        choice["candidate_frame_count"] = len(frame)
        choice["eligible_frame_count"] = len(eligible)
        choice["restricted_excluded_count"] = len(restricted)
        selected.append(choice)
        used_ids.add(choice["repository_id"])
        used_owners.add(choice["owner"])
    result = pd.DataFrame(selected)
    out = root / "results/selected_repositories.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(out, index=False)
    return result
