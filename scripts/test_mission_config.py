from __future__ import annotations

from pathlib import Path

import yaml

import batch_fill
import gddp
import import_node
import new_node
import validate


def _valid_node() -> dict:
    return {
        "schema_version": "1.0",
        "schema_type": "node",
        "node_id": "mission-node",
        "title": "Mission node",
        "type": "capability",
        "why": "Exercise mission-mode validation",
        "depends_on": [],
        "acceptance_criteria": [{"id": "works", "criterion": "mission mode works"}],
        "constraints": [],
        "allowed_execution_modes": ["factory_mission"],
        "required_artifacts": [],
        "status": "ready",
        "priority": "medium",
        "unlocks": [],
    }


def test_every_execution_mode_allowlist_contains_factory_mission():
    allowlists = (
        validate.VALID_EXEC_MODES,
        import_node.VALID_EXEC_MODES,
        new_node.VALID_EXEC_MODES,
        batch_fill.VALID_EXEC_MODES,
    )

    assert all("factory_mission" in modes for modes in allowlists)


def test_node_validator_accepts_and_retains_factory_mission():
    input_yaml = yaml.safe_dump(_valid_node(), sort_keys=False)
    node = yaml.safe_load(input_yaml)

    findings = validate.validate_node(
        Path("mission-node.yaml"),
        "graphs/test/nodes/mission-node.yaml",
        node,
    )

    assert findings == []
    assert node["allowed_execution_modes"] == ["factory_mission"]


def test_node_validator_rejects_mode_removed_from_injected_allowlist(monkeypatch):
    node = _valid_node()
    monkeypatch.setattr(
        validate,
        "VALID_EXEC_MODES",
        validate.VALID_EXEC_MODES - {"factory_mission"},
    )

    findings = validate.validate_node(
        Path("mission-node.yaml"),
        "graphs/test/nodes/mission-node.yaml",
        node,
    )

    errors = [finding for finding in findings if finding.rule == "exec_mode_enum"]
    assert len(errors) == 1
    assert errors[0].severity == "error"
    assert "factory_mission" in errors[0].message


def test_project_validator_accepts_positive_mission_sizing_fields(tmp_path, monkeypatch):
    root = tmp_path
    project_dir = root / "graphs" / "mission-project"
    (project_dir / "nodes").mkdir(parents=True)
    (project_dir / "project.yaml").write_text(
        """
schema_version: "1.0"
project_id: mission-project
repo: owner/repo
nodes: []
execution_policy:
  mission_engagement_size: 3
  mission_max_pairs: 5
""".lstrip()
    )
    monkeypatch.setattr(gddp, "ROOT", root)

    assert gddp.validate_project("mission-project") == 0


def test_project_validator_rejects_non_positive_mission_sizing_fields(
    tmp_path, monkeypatch
):
    root = tmp_path
    project_dir = root / "graphs" / "mission-project"
    (project_dir / "nodes").mkdir(parents=True)
    (project_dir / "project.yaml").write_text(
        """
schema_version: "1.0"
project_id: mission-project
repo: owner/repo
nodes: []
execution_policy:
  mission_engagement_size: 0
  mission_max_pairs: false
""".lstrip()
    )
    monkeypatch.setattr(gddp, "ROOT", root)

    assert gddp.validate_project("mission-project") == 1
