# Shape profile

A shape profile encodes what a project type should look like structurally. Profiles are optional context for the semantic verification agent. They do not mutate graph truth.

Shape profiles live in `profiles/<profile_id>.yaml`. This is a Wave 3 feature and is not yet implemented. The schema exists as a forward-looking definition of the structure.

Source: `schemas/v1/shape_profile.yaml`

## Fields

| Field | Type | Description |
|---|---|---|
| `profile_id` | string | Unique identifier for the profile |
| `description` | string | Human-readable description of the profile |
| `expected_node_chain` | list[string] | Expected sequence of node types in a project |
| `invariant_rules` | list[string] | Rules that must hold across the graph |
| `anti_patterns` | list[string] | Patterns that should not appear in the graph |

## Expected node chain

The `expected_node_chain` field defines the expected sequence of node types for a project matching this profile. For example, a profile might expect `spec`, then `implementation`, then `tests`. This is a structural expectation, not a strict requirement. The semantic verification agent uses it to flag graphs that deviate from the expected shape.

## Invariant rules

The `invariant_rules` field lists rules that must hold across the entire graph. These are checked by the semantic verification agent as part of its analysis. Examples from the schema:

- Graph legality must be preserved
- Acceptance criteria must not weaken

Invariant rules are structural constraints on graph truth. They do not change the graph. They flag violations for human review.

## Anti patterns

The `anti_patterns` field lists patterns that should not appear in the graph. Examples from the schema:

- Runtime silently mutates source graph
- Acceptance criteria removed without replacement

Anti patterns are the inverse of invariant rules. Where invariant rules state what must be true, anti patterns state what must not be true. Both feed into the semantic verification agent's analysis.

## Relationship to graph truth

Shape profiles do not mutate graph truth. They are read-only context for the semantic verification agent. The agent uses them to assess whether a graph conforms to expected structural patterns, but it cannot change the graph based on a profile. All graph truth changes remain human-owned, consistent with the core principle that [nodes](node.md) are human-authored.

## Implementation status

Shape profiles are a Wave 3 feature. The schema is defined in `schemas/v1/shape_profile.yaml`, but the runtime support for loading and using profiles is not yet implemented. The content will live in `profiles/<profile_id>.yaml` once implemented.

## Related pages

- [Primitives index](index.md)
- [Node](node.md)
- [The verification harness](../systems/verification-harness.md)
- [The schema system overview](../systems/schemas.md)
- [GDDP vocabulary](../overview/glossary.md)
