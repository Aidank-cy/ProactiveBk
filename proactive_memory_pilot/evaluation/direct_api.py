"""Stateless, single-request OpenAI-compatible API adapter for the pilot."""
import json
import os
from pathlib import Path
from urllib import request as http


def invoke(request, config):
    if config.get("seed") is not None:
        raise ValueError("seed is not supported by this direct API adapter")
    provider, model_id = config["model_name"].split("/", 1)
    provider_config = json.loads(Path(config["models_config_path"]).expanduser().read_text())["providers"][provider]
    key = os.environ.get(config["api_key_env"]) if config.get("api_key_env") else provider_config.get("apiKey")
    if not key or key.startswith("<"):
        raise ValueError("API key unavailable")
    base = (config.get("api_base_url") or provider_config["baseUrl"]).rstrip("/")
    body = {"model": model_id, "messages": request["input_messages"],
            "stream": False, "max_tokens": config["max_output_tokens"]}
    for target, source in (("temperature", "temperature"), ("top_p", "top_p")):
        if config.get(source) is not None:
            body[target] = config[source]
    req = http.Request(base + "/chat/completions", data=json.dumps(body).encode(),
                       headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
                       method="POST")
    try:
        with http.urlopen(req, timeout=config.get("timeout", 120)) as response:
            payload = json.load(response)
    except Exception as exc:
        # Some HTTP exceptions include request headers or echoed body. Do not expose secrets.
        raise RuntimeError(f"direct API request failed ({type(exc).__name__})") from None
    content = payload["choices"][0]["message"]["content"]
    if not isinstance(content, str):
        raise ValueError("API returned no assistant text")
    usage = payload.get("usage") or {}
    return {"raw_response": content, "input_tokens": usage.get("prompt_tokens"),
            "output_tokens": usage.get("completion_tokens"),
            "harness_version": "direct-openai-compatible-v1", "session_id": None}
