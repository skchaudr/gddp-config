"""Project list, YAML, and repo-resolve helpers for gddp."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import yaml

SCRIPTS_DIR = Path(__file__).resolve().parent
ROOT = SCRIPTS_DIR.parent

def _graph_projects(config_root: Path) -> list[str]:
    graphs = Path(config_root) / "graphs"
    if not graphs.is_dir():
        return []
    return sorted(
        d.name for d in graphs.iterdir()
        if d.is_dir() and (d / "project.yaml").is_file()
    )

def _resolve_project_repo(project: str, repo_path: str | None = None) -> Path | None:
    """Same candidate chain as verify node: flag, env root, sibling checkout."""
    import yaml

    repo_name = ""
    project_yaml = ROOT / "graphs" / project / "project.yaml"
    if project_yaml.is_file():
        with open(project_yaml) as f:
            repo_name = str((yaml.safe_load(f) or {}).get("repo", "")).split("/")[-1]
    candidates: list[Path] = []
    if repo_path:
        candidates.append(Path(repo_path).expanduser())
    env_root = os.environ.get("GDDP_REPO_ROOT") or os.environ.get("GDDP_REPOS_ROOT")
    if env_root and repo_name:
        candidates.append(Path(env_root).expanduser() / repo_name)
    if repo_name:
        candidates.append(ROOT.parent / repo_name)
    for candidate in candidates:
        if (candidate / ".git").exists():
            return candidate
    return None

def _resolve_repo_for_project(project: str, repo_path: str | None = None) -> Path | None:
    """Resolve a project's source checkout: --repo-path > env root > sibling."""
    project_yaml = ROOT / "graphs" / project / "project.yaml"
    if not project_yaml.is_file():
        return None
    try:
        with open(project_yaml) as f:
            proj = yaml.safe_load(f) or {}
    except Exception:
        return None
    repo_name = str(proj.get("repo", "")).split("/")[-1]
    candidates: list[Path] = []
    if repo_path:
        candidates.append(Path(repo_path).expanduser())
    env_root = os.environ.get("GDDP_REPO_ROOT") or os.environ.get("GDDP_REPOS_ROOT")
    if env_root and repo_name:
        candidates.append(Path(env_root).expanduser() / repo_name)
    if repo_name:
        candidates.append(ROOT.parent / repo_name)
    for c in candidates:
        if c.is_dir():
            return c
    return None

def _auto_base_commit(repo: Path) -> str | None:
    """Best-effort base for subject-diff evidence: HEAD~1, else HEAD."""
    for ref in ("HEAD~1", "HEAD"):
        proc = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", ref],
            capture_output=True, text=True, check=False,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout.strip()
    return None

def _load_project_doc(project_id: str) -> dict:
    with open(ROOT / "graphs" / project_id / "project.yaml") as f:
        return yaml.safe_load(f) or {}
