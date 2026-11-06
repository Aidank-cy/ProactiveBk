import logging
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from collector.github_client import GitHubClient
from collector.sample_prs import sample_prs
from collector.select_repositories import select_repositories


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text())
    selected = select_repositories(cfg, ROOT)
    client = GitHubClient(ROOT / ".cache/http", cfg["request_timeout_seconds"], cfg["max_retries"])
    sampled = sample_prs(client, selected, cfg, ROOT)
    print(f"Selected {len(selected)} repositories; sampled {len(sampled)} PRs")


if __name__ == "__main__":
    main()
