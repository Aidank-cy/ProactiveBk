"""Staged repository metadata checks, with API failures left pending."""
import base64
import json
import logging

LOG = logging.getLogger(__name__)


def count_issues_and_prs(client, store, cfg, limit=None):
    rows = [r for r in store.rows() if r["pr_count"] is None or r["issue_count"] is None]
    if limit is not None:
        rows = rows[:limit]
    batch_size = cfg["graphql_batch_size"]
    for offset in range(0, len(rows), batch_size):
        batch = rows[offset:offset + batch_size]
        fields = [f'r{i}: node(id: {json.dumps(json.loads(row["data"])["node_id"])}) {{ ... on Repository {{ pullRequests {{ totalCount }} issues {{ totalCount }} }} }}' for i, row in enumerate(batch)]
        query = "query { " + " ".join(fields) + " }"
        try:
            data = client.graphql(query)
            for i, row in enumerate(batch):
                node = data.get(f"r{i}") or {}
                prs = (node.get("pullRequests") or {}).get("totalCount")
                issues = (node.get("issues") or {}).get("totalCount")
                if prs is None or issues is None:
                    store.update(row["id"], error="GraphQL issue or PR count missing")
                else:
                    store.update(row["id"], pr_count=prs, issue_count=issues, error=None)
        except Exception as exc:
            LOG.error("count_batch_failed start=%s error=%s", offset, exc)
            for row in batch:
                try:
                    node_id = json.loads(row["data"])["node_id"]
                    data = client.graphql('query { r: node(id: ' + json.dumps(node_id) + ') { ... on Repository { pullRequests { totalCount } issues { totalCount } } } }')
                    node = data.get("r") or {}
                    prs = (node.get("pullRequests") or {}).get("totalCount")
                    issues = (node.get("issues") or {}).get("totalCount")
                    if prs is None or issues is None:
                        raise RuntimeError("GraphQL issue or PR count missing")
                    store.update(row["id"], pr_count=prs, issue_count=issues, error=None)
                except Exception as individual_exc:
                    store.update(row["id"], error=f"issue/PR count pending: {individual_exc}")
        if offset % 500 == 0:
            LOG.info("issue_pr_progress processed=%s total=%s", offset + len(batch), len(rows))


def load_osi_license_ids(client, root, expected_sha=None):
    """Pin SPDX's published license list blob SHA in the checkpoint."""
    path = root / ".cache/spdx_licenses.json"
    if path.exists():
        payload = json.loads(path.read_text())
        if expected_sha and payload["blob_sha"] != expected_sha:
            raise RuntimeError("Cached SPDX license list SHA does not match config")
    else:
        endpoint = f"repos/spdx/license-list-data/git/blobs/{expected_sha}" if expected_sha else "repos/spdx/license-list-data/contents/json/licenses.json"
        response, _ = client.get(endpoint)
        if response.get("encoding") != "base64":
            raise RuntimeError("SPDX license list content has unexpected encoding")
        if expected_sha and response["sha"] != expected_sha:
            raise RuntimeError("SPDX API returned a different license list blob")
        payload = {"blob_sha": response["sha"], "data": json.loads(base64.b64decode(response["content"]))}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload))
    ids = {x["licenseId"] for x in payload["data"]["licenses"] if x.get("isOsiApproved")}
    return ids, payload["blob_sha"]


def verify_licenses(client, store, cfg, root, limit=None):
    osi_ids, list_sha = load_osi_license_ids(client, root, cfg.get("spdx_license_list_blob_sha"))
    rows = []
    for row in store.rows():
        if row["license_status"] in ("verified", "non_osi", "missing"):
            continue
        if row["pr_count"] is None or row["issue_count"] is None:
            continue
        repo = json.loads(row["data"])
        if row["pr_count"] > cfg["pull_requests_min_exclusive"] and row["issue_count"] > cfg["issues_min_exclusive"] and repo["forks_count"] > cfg["forks_min_exclusive"]:
            rows.append(row)
    if limit is not None:
        rows = rows[:limit]
    LOG.info("license_stage candidates=%s spdx_blob=%s", len(rows), list_sha)
    for i, row in enumerate(rows):
        repo = json.loads(row["data"])
        full_name = repo["full_name"]
        try:
            current, _ = client.get(f"repos/{full_name}")
            license_info = current.get("license")
            if license_info is None:
                store.update(row["id"], license_status="missing", license_source_url=current.get("html_url"), error=None)
            else:
                spdx = license_info.get("spdx_id")
                status = "verified" if spdx in osi_ids else "unrecognized" if not spdx or spdx == "NOASSERTION" else "non_osi"
                store.update(row["id"], license_spdx=spdx, license_name=license_info.get("name"), license_status=status, license_source_url=license_info.get("url"), error=None)
        except Exception as exc:
            store.update(row["id"], license_status="pending", error=f"license check pending: {exc}")
        if i % 100 == 0:
            LOG.info("license_progress processed=%s total=%s", i + 1, len(rows))
    return list_sha
