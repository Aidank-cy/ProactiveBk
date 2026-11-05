"""Official REST API client with disk cache, retries, pagination, and resume."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import random
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
import yaml

LOG = logging.getLogger(__name__)


def github_token(allow_gh: bool = True) -> str | None:
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token:
        return token
    if allow_gh:
        try:
            result = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, timeout=8)
            if result.returncode == 0 and result.stdout.strip() and "\n" not in result.stdout.strip():
                return result.stdout.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        # Older gh releases predate `gh auth token` but retain OAuth credentials here.
        config_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        host_file = config_home / "gh" / "hosts.yml"
        try:
            hosts = yaml.safe_load(host_file.read_text()) or {}
            token = (hosts.get("github.com") or {}).get("oauth_token")
            return token if isinstance(token, str) and token.strip() else None
        except (OSError, yaml.YAMLError):
            return None
    return None


class GitHubError(RuntimeError):
    pass


class GitHubClient:
    def __init__(self, token: str, cache_dir: Path, timeout: int = 30, retries: int = 5,
                 rate_floor: int = 10):
        if not token:
            raise ValueError("GitHub authentication required")
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.timeout, self.retries, self.rate_floor = timeout, retries, rate_floor
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {token}",
                                     "Accept": "application/vnd.github+json",
                                     "X-GitHub-Api-Version": "2022-11-28",
                                     "User-Agent": "pr-feasibility-pilot/0.1"})

    def get(self, path: str, params: dict | None = None, *, refresh: bool = False):
        if path.startswith("http"):
            parsed = urlparse(path)
            if parsed.hostname != "api.github.com":
                raise GitHubError(f"Refusing non-GitHub API URL: {path}")
            url = path
        else:
            url = "https://api.github.com" + path
        params = params or {}
        key = hashlib.sha256(json.dumps([url, sorted(params.items())], sort_keys=True).encode()).hexdigest()
        target = self.cache_dir / f"{key}.json"
        if target.exists() and not refresh:
            return json.loads(target.read_text()), True
        for attempt in range(self.retries + 1):
            try:
                response = self.session.get(url, params=params, timeout=self.timeout)
            except requests.RequestException as exc:
                if attempt == self.retries:
                    raise GitHubError(f"GET {url}: {exc}") from exc
                delay = min(60, 2 ** attempt + random.random())
                LOG.warning("network_retry url=%s attempt=%s delay=%.1f", url, attempt, delay)
                time.sleep(delay)
                continue
            remaining = int(response.headers.get("X-RateLimit-Remaining", "9999"))
            if response.status_code == 200:
                data = response.json()
                temporary = target.with_suffix(".tmp")
                temporary.write_text(json.dumps(data, ensure_ascii=False))
                temporary.replace(target)
                if remaining < self.rate_floor:
                    reset = int(response.headers.get("X-RateLimit-Reset", "0"))
                    delay = max(0, reset - time.time()) + 1
                    LOG.warning("rate_limit_wait seconds=%.0f", delay)
                    time.sleep(delay)
                return data, False
            retryable = response.status_code in (403, 429, 500, 502, 503, 504)
            if not retryable or attempt == self.retries:
                raise GitHubError(f"GET {url}: HTTP {response.status_code}: {response.text[:300]}")
            retry_after = response.headers.get("Retry-After")
            reset = int(response.headers.get("X-RateLimit-Reset", "0"))
            delay = (max(1, reset - time.time()) + 1 if remaining == 0 else
                     float(retry_after) if retry_after else min(60, 2 ** attempt + random.random()))
            LOG.warning("api_retry url=%s status=%s attempt=%s delay=%.1f", url, response.status_code, attempt, delay)
            time.sleep(delay)
        raise AssertionError("unreachable")

    def pages(self, path: str, params: dict | None = None, *, max_pages: int | None = None):
        params = dict(params or {})
        params["per_page"] = 100
        page = 1
        while max_pages is None or page <= max_pages:
            params["page"] = page
            data, _ = self.get(path, params)
            if not isinstance(data, list):
                raise GitHubError(f"Expected paginated list at {path}")
            yield from data
            if len(data) < 100:
                break
            page += 1

    def search(self, path: str, query: str, *, page: int = 1, per_page: int = 100):
        data, _ = self.get(path, {"q": query, "page": page, "per_page": per_page})
        if data.get("incomplete_results"):
            LOG.warning("incomplete_search query=%s", query)
        return data
