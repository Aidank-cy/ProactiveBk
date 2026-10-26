#!/usr/bin/env python3
"""Download the unmodified official WildChat and SWE-chat dataset repositories.

Run with a Python environment containing huggingface_hub and hf_xet:
    python download_original_datasets.py

The three repositories download concurrently to folders beside this script.
Re-running the script resumes files already present through Hugging Face Hub.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
import argparse
import json
import os
import sys
import time

# The direct Hub HTTP route works on this host; the Xet CAS route stalls here.
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
os.environ.setdefault("HF_HUB_ETAG_TIMEOUT", "60")
os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "300")

from huggingface_hub import HfApi, snapshot_download
from huggingface_hub.errors import GatedRepoError, HfHubHTTPError


ROOT = Path(__file__).resolve().parent
DATASETS = {
    "WildChat-1M": "allenai/WildChat-1M",
    "WildChat-4.8M": "allenai/WildChat-4.8M",
    "SWE-chat": "SALT-NLP/SWE-chat",
}


def download(name: str, repo_id: str) -> dict:
    destination = ROOT / name
    attempt = 0
    while True:
        attempt += 1
        try:
            revision = HfApi().dataset_info(repo_id).sha
            print(f"[{name}] attempt {attempt}: {repo_id}@{revision} -> {destination}", flush=True)
            snapshot_download(
                repo_id=repo_id,
                repo_type="dataset",
                revision=revision,
                local_dir=destination,
                max_workers=2,
            )
            print(f"[{name}] complete", flush=True)
            return {"repository": repo_id, "revision": revision, "directory": name}
        except GatedRepoError:
            raise
        except Exception as exc:
            if isinstance(exc, HfHubHTTPError) and exc.response.status_code in (401, 403, 404):
                raise
            delay = min(10 * 2 ** min(attempt - 1, 5), 300)
            print(f"[{name}] attempt {attempt} failed: {exc!r}; retrying in {delay}s", file=sys.stderr, flush=True)
            time.sleep(delay)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", action="append", choices=DATASETS, help="only download this dataset (repeatable)")
    args = parser.parse_args()
    selected = {name: DATASETS[name] for name in (args.dataset or DATASETS)}
    results = {}
    failed = False
    with ThreadPoolExecutor(max_workers=len(selected)) as pool:
        futures = {pool.submit(download, name, repo): name for name, repo in selected.items()}
        for future in as_completed(futures):
            name = futures[future]
            try:
                results[name] = future.result()
            except Exception as exc:
                failed = True
                print(f"[{name}] FAILED: {exc!r}", file=sys.stderr, flush=True)

    if results:
        manifest = {
            "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
            "datasets": results,
        }
        (ROOT / "download_manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
