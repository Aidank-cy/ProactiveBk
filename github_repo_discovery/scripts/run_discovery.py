import argparse
import json
import logging
import sys
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from repo_discovery.aggregate_statistics import export
from repo_discovery.discover_repositories import discover
from repo_discovery.filter_repositories import count_issues_and_prs, verify_licenses
from repo_discovery.generate_report import generate_report
from repo_discovery.github_client import GitHubClient
from repo_discovery.store import Store


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limited", type=int, help="Process at most N repositories per filter stage; results are incomplete")
    parser.add_argument("--report-only", action="store_true")
    parser.add_argument("--skip-discovery", action="store_true")
    args = parser.parse_args()
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text())
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s', handlers=[logging.StreamHandler(), logging.FileHandler(ROOT / "discovery.log")])
    store = Store(ROOT / ".cache/discovery.sqlite")
    limit = args.limited or cfg.get("limited_repositories")
    stage_seconds = {}
    current_stage = None
    stage_started = None
    try:
        if not args.report_only:
            client = GitHubClient(ROOT / ".cache/http", cfg["request_timeout_seconds"], cfg["max_retries"], cfg["rate_limit_buffer_seconds"])
            stages = []
            if not args.skip_discovery:
                stages.append(("repository_search", lambda: discover(client, store, cfg)))
            stages.extend([
                ("issue_and_pull_request_counts", lambda: count_issues_and_prs(client, store, cfg, limit)),
                ("license_checks", lambda: verify_licenses(client, store, cfg, ROOT, limit)),
            ])
            for current_stage, action in stages:
                stage_started = time.monotonic()
                logging.info("stage_start name=%s", current_stage)
                action()
                stage_seconds[current_stage] = round(time.monotonic() - stage_started, 2)
                logging.info("stage_end name=%s seconds=%s", current_stage, stage_seconds[current_stage])
                current_stage = None
    finally:
        if current_stage and stage_started:
            stage_seconds[current_stage] = round(time.monotonic() - stage_started, 2)
        summary, qualified, pending = export(store, cfg, ROOT, limited=bool(limit))
        previous_summary_path = ROOT / "results/summary_statistics.json"
        if args.report_only and previous_summary_path.exists():
            # export just refreshed this file; historical timings are recoverable from the log.
            stage_seconds = {}
            for line in (ROOT / "discovery.log").read_text().splitlines():
                if "stage_end name=" in line and "seconds=" in line:
                    name = line.split("stage_end name=", 1)[1].split()[0]
                    stage_seconds[name] = float(line.rsplit("seconds=", 1)[1])
        summary["stage_seconds"] = stage_seconds
        spdx_path = ROOT / ".cache/spdx_licenses.json"
        if spdx_path.exists():
            summary["spdx_license_list_blob_sha"] = json.loads(spdx_path.read_text())["blob_sha"]
        (ROOT / "results/summary_statistics.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
        generate_report(summary, qualified, pending, ROOT)
        print(json.dumps({"verified_qualifying_count": summary["verified_qualifying_count"], "pending_count": summary["pending_count"], "complete_and_verified": summary["complete_and_verified"], "windows": summary["windows"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
