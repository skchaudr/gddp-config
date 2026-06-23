#!/usr/bin/env python3
"""llm_draft.py — LLM-assisted node field drafting.

Takes project context + existing nodes + new node metadata, asks an LLM to
draft the human-only fields (why, acceptance, constraints). Returns a dict
with suggested values, or None on failure.

Configuration via environment variables:
    GDDP_LLM_PROVIDER   deepseek | openai | anthropic | ollama (default: deepseek)
    GDDP_LLM_API_KEY    API key for the chosen provider
    GDDP_LLM_MODEL      model name (default: provider-dependent)
    GDDP_LLM_BASE_URL   optional override for custom endpoints

The function signature is clean and testable — no I/O in the function itself,
only in the provider adapters.

Usage:
    from llm_draft import draft_fields
    result = draft_fields(
        project_id="my-app",
        root=Path("/path/to/gddp-config"),
        node_id="auth-middleware",
        node_title="Auth Middleware",
        depends_on=["user-auth-model", "api-gateway"],
        existing_nodes=["user-auth-model", "api-gateway", "session-mgmt"],
    )
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Optional

try:
    import yaml
except ImportError:
    pass


def _load_project_context(root: Path, project_id: str) -> str:
    proj_yaml = root / "graphs" / project_id / "project.yaml"
    if not proj_yaml.exists():
        return ""
    with open(proj_yaml) as f:
        doc = yaml.safe_load(f) or {}
    parts = []
    if doc.get("project_name"):
        parts.append(f"Project: {doc['project_name']}")
    if doc.get("description") and doc["description"] != "REPLACE_ME":
        parts.append(f"Description: {doc['description']}")
    if doc.get("repo"):
        parts.append(f"Repo: {doc['repo']}")
    bp = doc.get("blueprint", {})
    if bp.get("vision") and bp["vision"] != "REPLACE_ME":
        parts.append(f"Vision: {bp['vision']}")
    if bp.get("architecture_notes") and bp["architecture_notes"] != "REPLACE_ME":
        parts.append(f"Architecture: {bp['architecture_notes']}")
    return "\n".join(parts)


def _load_existing_node_summaries(root: Path, project_id: str,
                                   node_ids: list[str]) -> str:
    nodes_dir = root / "graphs" / project_id / "nodes"
    if not nodes_dir.exists():
        return ""
    parts = []
    for nid in node_ids:
        path = nodes_dir / f"{nid}.yaml"
        if not path.exists():
            continue
        with open(path) as f:
            doc = yaml.safe_load(f) or {}
        entry = f"Node: {nid}"
        if doc.get("title"):
            entry += f" ({doc['title']})"
        if doc.get("why") and "REPLACE_ME" not in str(doc["why"]):
            entry += f"\n  Why: {doc['why'][:200]}"
        if doc.get("acceptance"):
            real = [a for a in doc["acceptance"] if isinstance(a, str) and "REPLACE_ME" not in a]
            if real:
                entry += f"\n  Acceptance ({len(real)} items): {real[:3]}"
        parts.append(entry)
    return "\n\n".join(parts)


PROMPT_TEMPLATE = """You are helping define a node in a project execution graph. The node represents one unit of work — a capability that must be built.

## Project Context
{project_context}

## Existing Nodes in This Project
{existing_nodes}

## New Node
- node_id: {node_id}
- title: {node_title}
- depends_on: {depends_on}
- type: capability

## Task
Draft the three human-only fields for this node. Be specific, verifiable, and grounded in the project context.

1. **why**: One paragraph explaining why this capability must exist. Reference what it enables downstream.

2. **acceptance**: A list of 3-7 verifiable bullets. Each must be testable. Use specific file paths, function names, or behavior descriptions where possible.

3. **constraints**: A list of 2-5 hard limits. These are non-negotiable rules the executor must follow. Include file path constraints, dependency constraints, and scope boundaries.

## Output Format
Return ONLY valid JSON with exactly these three keys:
```json
{{
  "why": "...",
  "acceptance": ["...", "..."],
  "constraints": ["...", "..."]
}}
```
"""


def _call_deepseek(prompt: str, api_key: str, base_url: str | None = None,
                   model: str | None = None) -> str:
    import urllib.request
    import urllib.error

    model = model or "deepseek-chat"
    url = (base_url or "https://api.deepseek.com") + "/v1/chat/completions"
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 1024,
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"DeepSeek API error {e.code}: {e.reason}") from e
    except Exception as e:
        raise RuntimeError(f"DeepSeek request failed: {e}") from e


def _call_openai(prompt: str, api_key: str, base_url: str | None = None,
                  model: str | None = None) -> str:
    import urllib.request
    import urllib.error

    model = model or "gpt-4o-mini"
    url = (base_url or "https://api.openai.com") + "/v1/chat/completions"
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 1024,
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"OpenAI API error {e.code}: {e.reason}") from e
    except Exception as e:
        raise RuntimeError(f"OpenAI request failed: {e}") from e


PROVIDERS = {
    "deepseek": _call_deepseek,
    "openai": _call_openai,
}


def _extract_json(text: str) -> Optional[dict]:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        start = 1 if lines[0].startswith("```") else 0
        end = len(lines)
        for i in range(len(lines) - 1, -1, -1):
            if lines[i].strip() == "```":
                end = i
                break
        text = "\n".join(lines[start:end])

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass

    return None


def draft_fields(project_id: str, root: Path, node_id: str, node_title: str,
                 depends_on: list[str], existing_nodes: list[str]) -> Optional[dict]:
    provider = os.environ.get("GDDP_LLM_PROVIDER", "deepseek")
    api_key = os.environ.get("GDDP_LLM_API_KEY", "")
    model = os.environ.get("GDDP_LLM_MODEL")
    base_url = os.environ.get("GDDP_LLM_BASE_URL")

    if not api_key and provider != "ollama":
        return None

    call_fn = PROVIDERS.get(provider)
    if not call_fn:
        return None

    project_context = _load_project_context(root, project_id)
    node_summaries = _load_existing_node_summaries(root, project_id, existing_nodes)

    prompt = PROMPT_TEMPLATE.format(
        project_context=project_context or "No project context available.",
        existing_nodes=node_summaries or "No existing nodes.",
        node_id=node_id,
        node_title=node_title,
        depends_on=", ".join(depends_on) if depends_on else "none",
    )

    try:
        response_text = call_fn(prompt, api_key, base_url, model)
    except Exception:
        return None

    parsed = _extract_json(response_text)
    if not parsed:
        return None

    result = {}
    if "why" in parsed and isinstance(parsed["why"], str):
        result["why"] = parsed["why"]
    if "acceptance" in parsed and isinstance(parsed["acceptance"], list):
        result["acceptance"] = [str(x) for x in parsed["acceptance"] if str(x).strip()]
    if "constraints" in parsed and isinstance(parsed["constraints"], list):
        result["constraints"] = [str(x) for x in parsed["constraints"] if str(x).strip()]

    return result if result else None


if __name__ == "__main__":
    p = Path(__file__).resolve().parent.parent
    import argparse
    ap = argparse.ArgumentParser(description="Test LLM draft for a node")
    ap.add_argument("--project", required=True)
    ap.add_argument("--node-id", required=True)
    ap.add_argument("--title", default=None)
    ap.add_argument("--deps", nargs="*", default=[])
    args = ap.parse_args()

    root = p
    title = args.title or args.node_id.replace("-", " ").title()
    existing = []
    nodes_dir = root / "graphs" / args.project / "nodes"
    if nodes_dir.exists():
        existing = [f.stem for f in nodes_dir.glob("*.yaml")]

    result = draft_fields(args.project, root, args.node_id, title, args.deps, existing)
    if result:
        print(json.dumps(result, indent=2))
    else:
        print("ERROR: draft failed", file=sys.stderr)
        sys.exit(1)
