import logging
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import date, timedelta

LOG = logging.getLogger(__name__)


def search_query(start, end, star_min, star_max):
    stars = f"stars:{star_min}..{star_max}" if star_max is not None else f"stars:>={star_min}"
    return f"{stars} created:{start}..{end} is:public"


def split_partition(start, end, star_min, star_max):
    a, b = date.fromisoformat(start), date.fromisoformat(end)
    if a < b:
        middle = a + (b - a) // 2
        return [(start, middle.isoformat(), star_min, star_max), ((middle + timedelta(days=1)).isoformat(), end, star_min, star_max)]
    if star_max is None:
        raise ValueError("Need a finite max star count to split a single date")
    if star_min >= star_max:
        raise ValueError("Single date and star count still exceeds API 1000-result cap")
    middle = (star_min + star_max) // 2
    return [(start, end, star_min, middle), (start, end, middle + 1, star_max)]


def discover(client, store, cfg):
    # A generous fixed upper bound is used only to create disjoint star partitions.
    queue = [(cfg["created_start"], cfg["created_end"], cfg["stars_min"], 1_000_000_000)]
    def fetch(partition, retry):
        start, end, lower, upper = partition
        key = search_query(start, end, lower, upper)
        try:
            first, _ = client.get("search/repositories", {"q": key, "per_page": cfg["search_page_size"], "page": 1}, refresh=retry)
            count = first["total_count"]
            incomplete = bool(first.get("incomplete_results"))
            if incomplete:
                return "pending", count, True, None, "incomplete_results=true"
            if count > 1000:
                return "split", count, False, None, None
            items = list(first["items"])
            page_count = (count + cfg["search_page_size"] - 1) // cfg["search_page_size"]
            def fetch_page(page):
                body, _ = client.get("search/repositories", {"q": key, "per_page": cfg["search_page_size"], "page": page}, refresh=retry)
                if body.get("incomplete_results"):
                    raise RuntimeError(f"incomplete_results on page {page}")
                return body["items"]
            with ThreadPoolExecutor(max_workers=cfg.get("search_page_workers", 1)) as executor:
                for page_items in executor.map(fetch_page, range(2, page_count + 1)):
                    items.extend(page_items)
            # Verify this leaf only after all pages are retrieved. Search results can change mid-run.
            if len(items) < count:
                raise RuntimeError(f"retrieved {len(items)} of {count} search matches")
            return "complete", count, False, items, None
        except Exception as exc:
            return "pending", None, False, None, str(exc)

    futures = {}
    with ThreadPoolExecutor(max_workers=cfg.get("search_partition_workers", 1)) as executor:
        while queue or futures:
            while queue and len(futures) < cfg.get("search_partition_workers", 1):
                partition = queue.pop()
                start, end, lower, upper = partition
                key = search_query(*partition)
                status = store.partition_status(key)
                if status == "complete":
                    continue
                if status == "split":
                    queue.extend(split_partition(*partition))
                    continue
                futures[executor.submit(fetch, partition, status == "pending")] = partition
            if not futures:
                continue
            done, _ = wait(futures, return_when=FIRST_COMPLETED)
            for future in done:
                partition = futures.pop(future)
                start, end, lower, upper = partition
                key = search_query(*partition)
                status, count, incomplete, items, error = future.result()
                if status == "complete":
                    eligible = [x for x in items if cfg["created_start"] <= x["created_at"][:10] <= cfg["created_end"] and x["stargazers_count"] >= cfg["stars_min"]]
                    store.add_repos(eligible)
                    LOG.info("search_leaf query=%s matches=%s unique_added=%s", key, count, len(eligible))
                elif status == "split":
                    queue.extend(split_partition(*partition))
                else:
                    LOG.error("search_failed query=%s error=%s", key, error)
                store.partition(key, start, end, lower, upper, count, incomplete, status, error)


def discovery_complete(store):
    rows = list(store.db.execute("SELECT status FROM partitions"))
    return bool(rows) and all(x[0] != "pending" for x in rows) and any(x[0] == "complete" for x in rows)
