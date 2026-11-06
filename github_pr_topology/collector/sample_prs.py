import json
import logging
import random
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

LOG = logging.getLogger(__name__)
REFERENCE = re.compile(r"(?:[\w.-]+/[\w.-]+)?#\d+")


def _write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(obj, ensure_ascii=False))
    temp.replace(path)


def _frame(client, full_name, cfg, root):
    path = root / "data/raw" / full_name.replace("/", "__") / "pr_frame.json"
    end = cfg.get("pr_observation_end") or datetime.now(timezone.utc).date().isoformat()
    if path.exists():
        saved = json.loads(path.read_text())
        if saved.get("observation_start") == cfg["pr_observation_start"] and saved.get("observation_end") == end:
            return saved
    items, truncated, pages = client.paginate(f"repos/{full_name}/pulls", {"state": "all", "sort": "created", "direction": "desc", "per_page": 100}, max_pages=(cfg["pr_frame_cap"] + 99) // 100)
    window = [x for x in items if cfg["pr_observation_start"] <= x["created_at"][:10] <= end]
    payload = {"items": window[:cfg["pr_frame_cap"]], "retrieved": len(items), "eligible": len(window), "truncated": truncated or len(items) > cfg["pr_frame_cap"], "pages": pages, "observation_start": cfg["pr_observation_start"], "observation_end": end, "frame_definition": "newest PRs by creation date, all states, bounded at pr_frame_cap; random within this frame"}
    _write_json(path, payload)
    return payload


def _signals(client, items, full_name, root):
    path = root / "data/raw" / full_name.replace("/", "__") / "interaction_signals.json"
    if path.exists():
        return json.loads(path.read_text())
    result = {}
    for start in range(0, len(items), 40):
        batch = items[start:start + 40]
        fields = [f'r{i}: node(id: {json.dumps(p["node_id"])}) {{ ... on PullRequest {{ reviews {{ totalCount }} commits {{ totalCount }} comments {{ totalCount }} reviewThreads {{ totalCount }} }} }}' for i, p in enumerate(batch)]
        try:
            response = client.graphql("query { " + " ".join(fields) + " }")
            for i, pr in enumerate(batch):
                node = response.get(f"r{i}") or {}
                result[str(pr["number"])] = {k: (node.get(k) or {}).get("totalCount") for k in ("reviews", "commits", "comments", "reviewThreads")}
        except Exception as exc:
            LOG.error("signal_batch_failed repo=%s start=%s error=%s", full_name, start, exc)
            for pr in batch:
                result[str(pr["number"])] = {"reviews": None, "commits": None, "comments": None, "reviewThreads": None}
    _write_json(path, result)
    return result


def _weighted_sample_without_replacement(items, weights, size, rng):
    pool = list(zip(items, weights))
    selected = []
    for _ in range(min(size, len(pool))):
        pick = rng.choices(range(len(pool)), weights=[max(0.01, w) for _, w in pool], k=1)[0]
        selected.append(pool.pop(pick)[0])
    return selected


def sample_prs(client, selected_repos, cfg, root):
    rows = []
    for repo in selected_repos.to_dict("records"):
        full_name = repo["full_name"]
        frame = _frame(client, full_name, cfg, root)
        items = frame["items"]
        needed = cfg["random_prs_per_repository"] + cfg["enriched_prs_per_repository"]
        if len(items) < needed:
            raise RuntimeError(f"{full_name}: only {len(items)} eligible PRs in bounded frame; replacement required")
        signals = _signals(client, items, full_name, root)
        rng = random.Random(f"{cfg['seed']}:{repo['repository_id']}")
        random_group = rng.sample(items, cfg["random_prs_per_repository"])
        random_ids = {x["number"] for x in random_group}
        remaining = [x for x in items if x["number"] not in random_ids]
        weights = []
        for p in remaining:
            s = signals.get(str(p["number"]), {})
            references = len(REFERENCE.findall((p.get("body") or "") + " " + (p.get("title") or "")))
            score = 1 + 2 * min(s.get("reviewThreads") or 0, 10) + min(s.get("reviews") or 0, 10) + min(s.get("commits") or 0, 10) + min(s.get("comments") or 0, 10) + min(references, 5)
            weights.append(float(score))
        enriched = _weighted_sample_without_replacement(remaining, weights, cfg["enriched_prs_per_repository"], rng)
        for group, prs in (("random", random_group), ("interaction_enriched", enriched)):
            for p in prs:
                s = signals.get(str(p["number"]), {})
                rows.append({"repository_id": repo["repository_id"], "repo": full_name, "pr_number": p["number"], "pr_node_id": p["node_id"], "pr_url": p["html_url"], "created_at": p["created_at"], "sampling_group": group, "sampling_seed": cfg["seed"], "frame_size": len(items), "frame_retrieved": frame["retrieved"], "frame_truncated": frame["truncated"], "random_selection_probability": cfg["random_prs_per_repository"] / len(items) if group == "random" else None, "enriched_marginal_probability_known": False if group != "random" else None, "signal_reviews": s.get("reviews"), "signal_review_threads": s.get("reviewThreads"), "signal_commits": s.get("commits"), "signal_comments": s.get("comments"), "processing_track": repo["processing_track"]})
        LOG.info("sampled repo=%s random=%s enriched=%s frame=%s truncated=%s", full_name, len(random_group), len(enriched), len(items), frame["truncated"])
        pd.DataFrame(rows).to_csv(root / "results/sampled_prs.csv", index=False)
    frame = pd.DataFrame(rows).sort_values(["repo", "sampling_group", "pr_number"])
    assert not frame.duplicated(["repo", "pr_number"]).any()
    frame.to_csv(root / "results/sampled_prs.csv", index=False)
    return frame
