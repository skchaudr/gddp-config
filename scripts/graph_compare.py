#!/usr/bin/env python3
"""
graph_compare.py — READ-ONLY graph comparison across gddp-config projects.

Walks graphs/*/ and prints a side-by-side table so you can hold practice
graphs up against the proven ones (vault-doctor, gddp-runtime). Reports the
quality dimensions that actually matter for dispatchability:

  - node count, status breakdown, type breakdown
  - edge stats (depends_on / unlocks), orphan + dangling edges, cycles
  - acceptance criteria counts (the fuel jobs/results key against)
  - discipline violations: non-verdict statuses, non-kebab-case acceptance IDs

This script NEVER writes, mutates, or validates-and-fixes anything. It only
reads. Run it as often as you like while iterating.

Usage:
    .venv/bin/python scripts/graph_compare.py
    .venv/bin/python scripts/graph_compare.py --graphs-dir graphs --project vault-doctor
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("PyYAML not found. Run with the repo venv: .venv/bin/python scripts/graph_compare.py")

VERDICT_STATUSES = {"pending", "ready", "complete", "deferred"}
KEBAB = __import__("re").compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def load_nodes(project_dir: Path) -> list[dict]:
    nodes_dir = project_dir / "nodes"
    if not nodes_dir.is_dir():
        return []
    out = []
    for f in sorted(nodes_dir.glob("*.yaml")):
        try:
            data = yaml.safe_load(f.read_text()) or {}
        except yaml.YAMLError as e:
            out.append({"node_id": f.stem, "_parse_error": str(e)})
            continue
        data["_file"] = f.name
        out.append(data)
    return out


def analyze(project_dir: Path) -> dict:
    nodes = load_nodes(project_dir)
    ids = {n.get("node_id") for n in nodes if n.get("node_id")}
    statuses, types = Counter(), Counter()
    dep_edges = unlock_edges = accept_total = 0
    violations: list[str] = []
    adj: dict[str, list[str]] = defaultdict(list)  # node -> depends_on targets

    for n in nodes:
        nid = n.get("node_id", n.get("_file", "?"))
        if "_parse_error" in n:
            violations.append(f"{nid}: YAML parse error")
            continue

        st = n.get("status")
        statuses[st] += 1
        if st not in VERDICT_STATUSES:
            violations.append(f"{nid}: non-verdict status '{st}' (expected {sorted(VERDICT_STATUSES)})")

        types[n.get("type", "?")] += 1

        deps = n.get("depends_on") or []
        unlocks = n.get("unlocks") or []
        dep_edges += len(deps)
        unlock_edges += len(unlocks)
        adj[nid] = list(deps)

        for d in deps:
            if d not in ids:
                violations.append(f"{nid}: depends_on dangling target '{d}'")
        for u in unlocks:
            if u not in ids:
                violations.append(f"{nid}: unlocks dangling target '{u}' (ok if a planned future node)")

        for a in (n.get("acceptance_criteria") or []):
            accept_total += 1
            aid = (a or {}).get("id")
            if not aid or not KEBAB.match(str(aid)):
                violations.append(f"{nid}: acceptance id '{aid}' is not kebab-case")

    # orphans: nodes nothing depends on AND that depend on nothing (isolated)
    depended_on = {t for targets in adj.values() for t in targets}
    orphans = [nid for nid in ids if nid not in depended_on and not adj.get(nid)]

    cycles = find_cycles(adj, ids)

    n_nodes = len([n for n in nodes if "_parse_error" not in n])
    return {
        "project": project_dir.name,
        "nodes": n_nodes,
        "statuses": statuses,
        "types": types,
        "dep_edges": dep_edges,
        "unlock_edges": unlock_edges,
        "accept_total": accept_total,
        "accept_per_node": round(accept_total / n_nodes, 1) if n_nodes else 0,
        "orphans": orphans,
        "cycles": cycles,
        "violations": violations,
    }


def find_cycles(adj: dict[str, list[str]], ids: set[str]) -> list[list[str]]:
    WHITE, GREY, BLACK = 0, 1, 2
    color = {nid: WHITE for nid in ids}
    cycles: list[list[str]] = []

    def dfs(u: str, stack: list[str]):
        color[u] = GREY
        stack.append(u)
        for v in adj.get(u, []):
            if v not in color:
                continue
            if color[v] == GREY:
                cycles.append(stack[stack.index(v):] + [v])
            elif color[v] == WHITE:
                dfs(v, stack)
        stack.pop()
        color[u] = BLACK

    for nid in ids:
        if color[nid] == WHITE:
            dfs(nid, [])
    return cycles


def print_report(results: list[dict]) -> None:
    if not results:
        print("No project graphs found.")
        return

    hdr = f"{'project':<18}{'nodes':>6}{'edges(d/u)':>12}{'accept':>8}{'/node':>7}{'cycles':>8}{'viol':>6}"
    print("\n" + hdr)
    print("-" * len(hdr))
    for r in results:
        print(
            f"{r['project']:<18}{r['nodes']:>6}"
            f"{str(r['dep_edges']) + '/' + str(r['unlock_edges']):>12}"
            f"{r['accept_total']:>8}{r['accept_per_node']:>7}"
            f"{len(r['cycles']):>8}{len(r['violations']):>6}"
        )

    for r in results:
        print(f"\n### {r['project']}")
        print(f"  status : {dict(r['statuses'])}")
        print(f"  type   : {dict(r['types'])}")
        if r["orphans"]:
            print(f"  orphans (isolated, no edges in/out): {r['orphans']}")
        if r["cycles"]:
            for c in r["cycles"]:
                print(f"  CYCLE  : {' -> '.join(c)}")
        if r["violations"]:
            for v in r["violations"]:
                print(f"  ! {v}")
        else:
            print("  clean: no discipline violations")
    print("\nReminder: this is a quality lens, not the authoritative validator.")
    print("Run `gddp node validate` for the schema gate.\n")


def main() -> None:
    ap = argparse.ArgumentParser(description="Read-only comparison across gddp graphs.")
    ap.add_argument("--graphs-dir", default="graphs")
    ap.add_argument("--project", action="append", help="limit to project(s); repeatable")
    args = ap.parse_args()

    root = Path(args.graphs_dir)
    if not root.is_dir():
        sys.exit(f"graphs dir not found: {root.resolve()}")

    projects = sorted(
        p for p in root.iterdir()
        if p.is_dir() and not p.name.startswith("_") and (p / "nodes").is_dir()
    )
    if args.project:
        wanted = set(args.project)
        projects = [p for p in projects if p.name in wanted]

    results = [analyze(p) for p in projects]
    print_report(results)


if __name__ == "__main__":
    main()
