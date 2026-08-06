"""Regression tests for scripts/validate.py list-item type checks.

Pins the vm-harness-audit incident (2026-08-05): an unquoted
`- Read-only: inspect and report only` constraint parses as a single-key
mapping, not a string. The runtime verifier used to crash on that dict
(gddp-runtime 185e6fe made it warn+skip); the authoring layer must REJECT
it, because warn+skip means a constraint silently stops constraining.
"""

from pathlib import Path

from validate import validate_node


def _valid_doc() -> dict:
    return {
        "schema_version": "1.0",
        "schema_type": "node",
        "node_id": "test-node",
        "title": "Test node",
        "type": "task",
        "why": "regression fixture",
        "depends_on": [],
        "acceptance_criteria": [{"id": "ok", "criterion": "something holds"}],
        "constraints": [],
        "allowed_execution_modes": ["pi"],
        "required_artifacts": [],
        "status": "draft",
        "priority": "normal",
        "unlocks": [],
    }


def _validate(doc: dict):
    return validate_node(Path("test-node.yaml"), "graphs/p/nodes/test-node.yaml", doc)


class TestImplicitMappingPromotion:
    def test_unquoted_colon_constraint_is_error(self):
        doc = _valid_doc()
        # What YAML produces for: - Read-only: inspect and report only
        doc["constraints"] = [{"Read-only": "inspect and report only"}]
        findings = _validate(doc)
        hits = [f for f in findings if f.rule == "implicit_mapping_in_list"]
        assert len(hits) == 1
        assert hits[0].severity == "error"
        assert "quote the string" in hits[0].message
        assert "Read-only: inspect and report only" in hits[0].message

    def test_quoted_colon_constraint_is_clean(self):
        doc = _valid_doc()
        doc["constraints"] = ["Read-only: inspect and report only"]
        findings = _validate(doc)
        assert not [f for f in findings if f.rule == "implicit_mapping_in_list"]

    def test_applies_to_all_list_fields(self):
        for field in ("depends_on", "unlocks", "constraints",
                      "allowed_execution_modes", "required_artifacts"):
            doc = _valid_doc()
            doc[field] = [{"Note": "unquoted colon"}]
            findings = _validate(doc)
            hits = [f for f in findings if f.rule == "implicit_mapping_in_list"]
            assert hits and all(f.severity == "error" for f in hits), field

    def test_non_dict_non_string_is_error(self):
        doc = _valid_doc()
        doc["constraints"] = [42]
        findings = _validate(doc)
        hits = [f for f in findings if f.rule == "list_of_strings"]
        assert len(hits) == 1
        assert hits[0].severity == "error"

    def test_non_string_acceptance_criterion_is_error(self):
        doc = _valid_doc()
        doc["acceptance_criteria"] = [{"id": "bad", "criterion": {"Nested": "dict"}}]
        findings = _validate(doc)
        hits = [f for f in findings if f.rule == "acceptance_criterion_type"]
        assert len(hits) == 1
        assert hits[0].severity == "error"


def test_ready_with_unsatisfied_deps_is_error():
    """Authoring a dependent as 'ready' strands it (advance_frontier only
    transitions pending nodes; a settled project reads dormant), so the
    validator must refuse ready-with-unsatisfied-deps (2026-08-06 stall)."""
    from validate import cross_node_findings
    docs = {
        "a": {"node_id": "a", "status": "ready", "depends_on": [], "unlocks": ["b"]},
        "b": {"node_id": "b", "status": "ready", "depends_on": ["a"], "unlocks": []},
    }
    findings = cross_node_findings("proj", docs)
    assert ("error", "ready_with_unsatisfied_deps") in [
        (f.severity, f.rule) for f in findings
    ]


def test_ready_with_satisfied_deps_passes():
    from validate import cross_node_findings
    docs = {
        "a": {"node_id": "a", "status": "provisional", "depends_on": [], "unlocks": ["b"]},
        "b": {"node_id": "b", "status": "ready", "depends_on": ["a"], "unlocks": []},
    }
    findings = cross_node_findings("proj", docs)
    assert ("error", "ready_with_unsatisfied_deps") not in [
        (f.severity, f.rule) for f in findings
    ]
