#!/usr/bin/env python3
"""Validate ARMS graph.json + required frontmatter fields (node 02)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

NODE_TYPES = {"root", "hub", "skill", "artifact", "routine", "app"}
EDGE_KINDS = {"router_leaf", "parent_child"}
FM_REQUIRED = ("title", "tags", "type", "dates", "model", "path")


def fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)
    raise SystemExit(1)


def validate(graph: dict) -> None:
    if graph.get("schema_version") != "1.0":
        fail("schema_version must be '1.0'")
    for key in ("generated_at", "vault_root", "nodes", "edges"):
        if key not in graph:
            fail(f"missing top-level key: {key}")
    nodes = graph["nodes"]
    edges = graph["edges"]
    if not isinstance(nodes, list) or not nodes:
        fail("nodes must be a non-empty list")
    if not isinstance(edges, list):
        fail("edges must be a list")

    ids = set()
    types_seen = set()
    for i, node in enumerate(nodes):
        for k in ("id", "type", "label", "frontmatter"):
            if k not in node:
                fail(f"nodes[{i}] missing {k}")
        if node["id"] in ids:
            fail(f"duplicate id: {node['id']}")
        ids.add(node["id"])
        if node["type"] not in NODE_TYPES:
            fail(f"nodes[{i}] bad type: {node['type']}")
        types_seen.add(node["type"])
        fm = node["frontmatter"]
        for field in FM_REQUIRED:
            if field not in fm:
                fail(f"nodes[{i}] frontmatter missing {field}")
        if not isinstance(fm["title"], str) or not fm["title"]:
            fail(f"nodes[{i}] title must be non-empty string")
        if not isinstance(fm["tags"], list):
            fail(f"nodes[{i}] tags must be a list")
        if fm["type"] not in NODE_TYPES:
            fail(f"nodes[{i}] frontmatter.type invalid")
        if fm["type"] != node["type"]:
            fail(f"nodes[{i}] type/frontmatter.type mismatch")
        dates = fm["dates"]
        if not isinstance(dates, dict) or "created" not in dates or "modified" not in dates:
            fail(f"nodes[{i}] dates must have created and modified")
        if not isinstance(fm["path"], str) or not fm["path"]:
            fail(f"nodes[{i}] path must be non-empty string")

    if "root" not in types_seen:
        fail("graph must contain at least one root node")

    for i, edge in enumerate(edges):
        for k in ("from", "to", "kind"):
            if k not in edge:
                fail(f"edges[{i}] missing {k}")
        if edge["kind"] not in EDGE_KINDS:
            fail(f"edges[{i}] bad kind: {edge['kind']}")
        if edge["from"] not in ids:
            fail(f"edges[{i}] from unknown: {edge['from']}")
        if edge["to"] not in ids:
            fail(f"edges[{i}] to unknown: {edge['to']}")
        if edge["from"] == edge["to"]:
            fail(f"edges[{i}] self-loop")

    # DAG: no cycles
    adj: dict[str, list[str]] = {n: [] for n in ids}
    for e in edges:
        adj[e["from"]].append(e["to"])
    state = {n: 0 for n in ids}

    def visit(n: str) -> None:
        if state[n] == 1:
            fail(f"cycle involving {n}")
        if state[n] == 2:
            return
        state[n] = 1
        for c in adj[n]:
            visit(c)
        state[n] = 2

    for n in ids:
        visit(n)

    print(f"OK: {len(nodes)} nodes, {len(edges)} edges")


def main() -> None:
    here = Path(__file__).resolve().parent
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else here / "02-sample-graph.json"
    data = json.loads(path.read_text())
    validate(data)


if __name__ == "__main__":
    main()
