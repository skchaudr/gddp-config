#!/usr/bin/env python3
"""Compact fzf preview cards — a few lines, never a YAML dump.

Usage:
    fzf_preview.py node <root> <project> <node_id>
    fzf_preview.py project <root> <project_id>
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

try:
    import yaml
except ImportError:
    print("pyyaml missing")
    sys.exit(0)


def _load(path: Path) -> dict | None:
    if not path.is_file():
        print(f"(no file: {path.name})")
        return None
    try:
        data = yaml.safe_load(path.read_text()) or {}
    except Exception as exc:
        print(f"(unreadable: {exc})")
        return None
    return data if isinstance(data, dict) else {}


def _wrap(text: str, width: int = 78, lines: int = 3) -> list[str]:
    blob = " ".join(str(text or "").split())
    if not blob:
        return []
    return textwrap.wrap(blob, width=width)[:lines]


def preview_node(root: Path, project: str, node_id: str) -> None:
    data = _load(root / "graphs" / project / "nodes" / f"{node_id}.yaml")
    if data is None:
        return
    title = str(data.get("title") or node_id)
    status = str(data.get("status") or "?")
    kind = str(data.get("type") or "")
    priority = str(data.get("priority") or "")
    meta = "  ·  ".join(p for p in (status, kind, priority) if p)
    print(title)
    print(meta)
    why_lines = _wrap(str(data.get("why") or ""))
    if why_lines:
        print()
        print("\n".join(why_lines))


def preview_project(root: Path, project_id: str) -> None:
    data = _load(root / "graphs" / project_id / "project.yaml")
    if data is None:
        return
    name = str(data.get("project_name") or project_id)
    nodes = data.get("nodes") or []
    count = len(nodes) if isinstance(nodes, list) else 0
    print(name)
    print(f"{count} node{'s' if count != 1 else ''}")
    desc_lines = _wrap(str(data.get("description") or ""))
    if desc_lines:
        print()
        print("\n".join(desc_lines))


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print("usage: fzf_preview.py node|project ...")
        return 0
    kind = argv[1]
    if kind == "node" and len(argv) >= 5:
        preview_node(Path(argv[2]), argv[3], argv[4])
        return 0
    if kind == "project" and len(argv) >= 4:
        preview_project(Path(argv[2]), argv[3])
        return 0
    print(f"(unknown preview: {kind})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
