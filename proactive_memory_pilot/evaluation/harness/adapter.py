"""Thin adapter over VibeLifeBench's pinned Terrarium OpenClawAgent."""
import json
import os
import sys
from pathlib import Path

VIBELIFE = Path(os.environ.get("VIBELIFE_ROOT", Path(__file__).resolve().parents[3] / "VibeLifeBench"))
SITE = VIBELIFE / ".venv/lib/python3.12/site-packages"
if str(SITE) not in sys.path:
    sys.path.insert(0, str(SITE))


def invoke(request, config):
    from terrarium.agent.openclaw import OpenClawAgent, CONFIG_PATH
    from terrarium.environment.environment import ComposableEnvironment
    from terrarium.models.trajectory import TextBlock, ToolUseBlock

    models_path = Path(config["models_config_path"]).expanduser().resolve()
    model_config = json.loads(models_path.read_text())
    provider, model_id = config["model_name"].split("/", 1)
    model = next(m for m in model_config["providers"][provider]["models"] if m["id"] == model_id)
    provider_config = model_config["providers"][provider]
    env_name = config.get("api_key_env")
    if env_name:
        provider_config["apiKey"] = os.environ[env_name]
    if not provider_config.get("apiKey") or provider_config["apiKey"].startswith("<"):
        raise ValueError("API key unavailable")
    if config.get("api_base_url"):
        provider_config["baseUrl"] = config["api_base_url"]
    # OpenClaw model params are passed by its native model config. No direct API call.
    params = model.setdefault("params", {})
    if config.get("temperature") is not None:
        params["temperature"] = config["temperature"]
    if config.get("top_p") is not None:
        params["topP"] = config["top_p"]
    if config.get("max_output_tokens") is not None:
        model["maxTokens"] = config["max_output_tokens"]
    if config.get("seed") is not None:
        raise ValueError("seed is not supported by this harness adapter")
    agent = OpenClawAgent(model=config["model_name"], models_config_path=str(models_path),
                          system_prompt=request["input_messages"][0]["content"])
    agent._models_config = model_config
    env = ComposableEnvironment(["workspace"], config={"workspace": agent.workspace_config()})
    try:
        env.start()
        agent.setup(env.workspace, {})
        cfg = json.loads(env.workspace.fs.read_file(CONFIG_PATH))
        cfg["tools"] = {"deny": ["*"]}
        cfg["agents"]["defaults"]["compaction"] = {"mode": "off"}
        env.workspace.fs.write_file(CONFIG_PATH, json.dumps(cfg).encode())
        original_exec = env.workspace.shell.exec
        def timed_exec(command, **kw):
            result = original_exec(command, timeout=config.get("timeout"), **kw)
            if result.exit_code != 0:
                raise RuntimeError(f"OpenClaw CLI exited {result.exit_code}: {result.stderr[:200]}")
            return result
        env.workspace.shell.exec = timed_exec
        result = agent.act(request["input_prompt"])
        if any(isinstance(b, ToolUseBlock) for m in result.messages for b in
               (m.content if isinstance(m.content, list) else [])):
            raise RuntimeError("tool use detected; request invalid")
        answers = [b.text for m in result.messages if m.role == "assistant" for b in
                   (m.content if isinstance(m.content, list) else []) if isinstance(b, TextBlock)]
        if not answers:
            raise RuntimeError("no assistant text")
        return {"raw_response": answers[-1], "input_tokens": result.input_tokens or None,
                "output_tokens": result.output_tokens or None,
                "harness_version": f"terrarium:7d641ea/openclaw:{agent.version()}",
                "session_id": agent._session_id}
    finally:
        env.stop()
