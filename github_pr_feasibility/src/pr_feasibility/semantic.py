"""Optional OpenAI-compatible classifier; sends only cutoff context and one later candidate."""
from __future__ import annotations

import json
import os

import requests


def annotate_cutoff(cutoff: dict, cfg: dict) -> dict | None:
    if cfg.get("llm_provider", "none") == "none":
        return None
    if cfg["llm_provider"] != "openai_compatible":
        raise ValueError("llm_provider must be none or openai_compatible")
    endpoint = cfg.get("llm_endpoint")
    model = cfg.get("llm_model")
    key = os.environ.get(cfg.get("llm_api_key_env", "OPENAI_API_KEY"))
    if not endpoint or not model or not key:
        raise ValueError("llm_endpoint, llm_model, and configured API key are required")
    prompt = {"historical_context_only": cutoff["context_preview"],
              "proposed_later_human_requirement": cutoff["future_requirement_candidates"][0]["text"]}
    response = requests.post(endpoint, headers={"Authorization": f"Bearer {key}"}, json={
        "model": model, "temperature": 0,
        "messages": [{"role": "system", "content": "Evaluate one possible implicit coding requirement. Return JSON with historical_grounding, contextual_inferability, action_relevance (each yes/no/uncertain), and a brief rationale. Treat later feedback as a proposed requirement, not as proof of inferability. Do not assume unavailable future changes."},
                     {"role": "user", "content": json.dumps(prompt)}]}, timeout=30)
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]
    try:
        result = json.loads(content)
    except json.JSONDecodeError:
        result = {"raw_response": content, "parse_error": True}
    result["status"] = "llm_assisted_unverified"
    return result
