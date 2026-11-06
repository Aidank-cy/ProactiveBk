import hashlib
import json
import logging
import os
import random
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
import yaml

LOG = logging.getLogger(__name__)


def github_token():
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        return token
    path = Path.home() / ".config/gh/hosts.yml"
    if path.exists():
        return (yaml.safe_load(path.read_text()) or {}).get("github.com", {}).get("oauth_token")
    return None


class GitHubClient:
    def __init__(self, cache_dir, timeout=45, retries=5, buffer=3):
        token = github_token()
        if not token:
            raise RuntimeError("GitHub authentication unavailable: set GITHUB_TOKEN or run gh auth login")
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "github-repo-discovery-study"})
        self.cache = Path(cache_dir)
        self.cache.mkdir(parents=True, exist_ok=True)
        self.timeout, self.retries, self.buffer = timeout, retries, buffer
        self.last_headers = {}

    def request(self, method, path, *, params=None, data=None, refresh=False):
        url = path if path.startswith("https://") else "https://api.github.com/" + path.lstrip("/")
        identity = json.dumps([method, url, params, data], sort_keys=True, separators=(",", ":"))
        key = hashlib.sha256(identity.encode()).hexdigest()
        cache_file = self.cache / key[:2] / (key + ".json")
        if cache_file.exists() and not refresh:
            payload = json.loads(cache_file.read_text())
            self.last_headers = payload.get("headers", {})
            return payload["body"], payload.get("headers", {})
        for attempt in range(self.retries + 1):
            try:
                response = self.session.request(method, url, params=params, json=data, timeout=self.timeout)
                self.last_headers = dict(response.headers)
                if response.status_code in (403, 429) and (response.headers.get("x-ratelimit-remaining") == "0" or "rate limit" in response.text.lower()):
                    reset = int(response.headers.get("x-ratelimit-reset", "0"))
                    delay = max(5, reset - time.time() + self.buffer) if reset else min(90, 2 ** attempt + random.random())
                    LOG.warning("rate_limit url=%s sleep=%.1f", url, delay)
                    time.sleep(delay)
                    continue
                if response.status_code in (500, 502, 503, 504, 429):
                    raise requests.HTTPError(f"HTTP {response.status_code}: {response.text[:300]}")
                response.raise_for_status()
                body = response.json()
                if isinstance(body, dict) and body.get("errors") and path == "graphql":
                    raise RuntimeError(f"GraphQL errors: {body['errors'][:2]}")
                cache_file.parent.mkdir(parents=True, exist_ok=True)
                tmp = cache_file.with_suffix(".tmp")
                tmp.write_text(json.dumps({"body": body, "headers": {"link": response.headers.get("link", ""), "x-ratelimit-remaining": response.headers.get("x-ratelimit-remaining", "")}, "collected_at": datetime.now(timezone.utc).isoformat()}))
                tmp.replace(cache_file)
                return body, dict(response.headers)
            except (requests.RequestException, RuntimeError) as exc:
                if attempt == self.retries:
                    raise RuntimeError(f"GitHub request failed after {attempt + 1} tries: {method} {url}: {exc}") from exc
                delay = min(90, 2 ** attempt + random.random())
                LOG.warning("request_retry url=%s attempt=%s delay=%.1f error=%s", url, attempt + 1, delay, exc)
                time.sleep(delay)

    def get(self, path, params=None, refresh=False):
        return self.request("GET", path, params=params, refresh=refresh)

    def graphql(self, query):
        return self.request("POST", "graphql", data={"query": query})[0]["data"]
