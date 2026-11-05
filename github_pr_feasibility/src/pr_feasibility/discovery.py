"""Language and domain agnostic repository and PR sampling frames."""
from __future__ import annotations

import logging
import random
from datetime import date, datetime, timedelta, timezone

LOG = logging.getLogger(__name__)
STRATA = ((500, 1999), (2000, 9999), (10000, None))


def iso_date(value: str | None) -> date:
    return date.fromisoformat(value) if value else datetime.now(timezone.utc).date()


def discover_repositories(client, cfg):
    """Search the first configured pages sorted by recent update; preserve the entire frame."""
    cutoff = iso_date(cfg.get("observation_end")) - timedelta(days=cfg["pushed_within_days"])
    rows = []
    for low, high in STRATA:
        label = f"{low}-{high or 'plus'}"
        star_filter = f"stars:{low}..{high}" if high else f"stars:>={low}"
        query = f"{star_filter} forks:>={cfg['forks_min']} archived:false fork:false pushed:>={cutoff}"
        for page in range(1, cfg["repository_search_pages_per_stratum"] + 1):
            result = client.search("/search/repositories", query, page=page,
                                   per_page=cfg["repository_search_page_size"])
            for item in result.get("items", []):
                rows.append({"stratum": label, "search_page": page, "search_query": query,
                             "search_total_count": result.get("total_count"),
                             "search_incomplete": result.get("incomplete_results", False),
                             "full_name": item["full_name"], "url": item["html_url"],
                             "stars": item["stargazers_count"], "forks": item["forks_count"],
                             "size_kb": item["size"], "created_at": item["created_at"],
                             "pushed_at": item.get("pushed_at"), "updated_at": item["updated_at"],
                             "archived": item["archived"], "fork": item["fork"],
                             "private": item["private"], "open_issues_count": item.get("open_issues_count"),
                             "subscribers_count": item.get("subscribers_count"),
                             "selected": False, "replacement_reason": "", "recent_merged_prs": None,
                             "recent_pr_activity_status": "not_queried_unless_evaluated"})
            if len(result.get("items", [])) < cfg["repository_search_page_size"]:
                break
    dedup = {row["full_name"]: row for row in rows}
    rows = list(dedup.values())
    for row in rows:
        pushed = row["pushed_at"] and iso_date(row["pushed_at"][:10]) >= cutoff
        row["eligible"] = bool(not row["private"] and not row["archived"] and not row["fork"]
                               and row["stars"] >= cfg["stars_min"] and row["forks"] >= cfg["forks_min"]
                               and pushed)
    return rows


def repository_order(rows, cfg):
    """Reproducible shuffled order, with distinct owners preferred within each stratum."""
    rng = random.Random(cfg["seed"])
    order = {}
    for low, high in STRATA:
        label = f"{low}-{high or 'plus'}"
        subset = sorted((r for r in rows if r["stratum"] == label and r["eligible"]),
                        key=lambda r: r["full_name"])
        rng.shuffle(subset)
        order[label] = subset
    return order


def merged_pr_frame(client, repo: str, start: date, end: date):
    """Recursively shard merge-date search to avoid GitHub's 1000-result search cap."""
    def collect(a, b):
        query = f"repo:{repo} is:pr is:merged merged:{a}..{b}"
        first = client.search("/search/issues", query)
        count = first.get("total_count", 0)
        if count > 1000:
            if a == b:
                LOG.warning("incomplete_pr_frame repo=%s day=%s count=%s", repo, a, count)
                return first.get("items", []), [{"query": query, "count": count, "complete": False}]
            mid = a + timedelta(days=(b - a).days // 2)
            left, lm = collect(a, mid)
            right, rm = collect(mid + timedelta(days=1), b)
            return left + right, lm + rm
        items = first.get("items", [])
        for page in range(2, (count + 99) // 100 + 1):
            items.extend(client.search("/search/issues", query, page=page).get("items", []))
        return items, [{"query": query, "count": count,
                        "complete": not first.get("incomplete_results", False) and len(items) >= count}]
    if end < start:
        raise ValueError("observation_end precedes observation_start")
    items, shards = collect(start, end)
    dedup = {item["number"]: item for item in items}
    return list(dedup.values()), shards


def sample_prs(items, cfg, repo, *, seed_offset=0, client=None):
    """Random baseline plus deterministic interaction-prioritized enrichment."""
    rng = random.Random(cfg["seed"] + seed_offset)
    candidates = sorted(items, key=lambda x: x["number"])
    n_random = cfg["random_prs_per_repository"]
    n_enriched = cfg["enriched_prs_per_repository"]
    if len(candidates) < n_random + n_enriched:
        return [], f"only {len(candidates)} merged PRs; need {n_random + n_enriched}"
    chosen = rng.sample(candidates, n_random)
    chosen_ids = {x["number"] for x in chosen}
    remaining = [x for x in candidates if x["number"] not in chosen_ids]
    # Screen a bounded pool by issue discussion, then enrich using PR metadata when a client is available.
    pool = sorted(remaining, key=lambda x: (-x.get("comments", 0), x["number"]))[:max(
        n_enriched, n_enriched * cfg.get("enrichment_pool_multiplier", 4))]
    signals = {}
    for item in pool:
        signal = {"issue_comments": item.get("comments", 0), "review_comments": None, "commits": None}
        if client is not None:
            try:
                pr, _ = client.get(f"/repos/{repo}/pulls/{item['number']}")
                signal.update(review_comments=pr.get("review_comments", 0), commits=pr.get("commits", 0))
            except Exception as exc:
                LOG.warning("enrichment_metadata_unavailable repo=%s pr=%s error=%s", repo, item["number"], exc)
        signals[item["number"]] = signal
    enriched = sorted(pool, key=lambda x: (-(signals[x["number"]]["review_comments"] or 0),
                                           -(signals[x["number"]]["commits"] or 0),
                                           -x.get("comments", 0), x["number"]))[:n_enriched]
    records = []
    for group, subset in (("random", chosen), ("interaction_enriched", enriched)):
        for item in subset:
            records.append({"repository": repo, "number": item["number"], "url": item["html_url"],
                            "sampling_group": group,
                            "selection_probability": n_random / len(candidates) if group == "random" else None,
                            "sampling_frame_size": len(candidates),
                            "sampling_signal": signals.get(item["number"]) if group != "random" else None,
                            "enrichment_rule": "top issue-comment pool, then review comments, commits, issue comments" if group != "random" else "uniform random",
                            "created_at": item.get("created_at"), "closed_at": item.get("closed_at")})
    return records, None
