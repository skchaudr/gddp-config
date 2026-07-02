# GDDP Obsidian Vault

Self-contained Obsidian vault for graph visibility. Open this folder directly in Obsidian.

## Regenerate notes

```bash
cd /path/to/gddp-config
.venv/bin/python scripts/gddp.py obsidian export
```

Or one project:

```bash
.venv/bin/python scripts/gddp.py obsidian export --project aa-cli
```

## One-way sync

- **Source of truth:** `graphs/<project>/nodes/*.yaml` in gddp-config
- **Generated:** `GDDP/graphs/<project>/<node>.md` in this vault
- **Editable in Obsidian:** only `verified` and `owned` in note frontmatter
- Everything else is overwritten on export — edit YAML, then re-export

## Graph View filters

Per-project graph:

```
path:GDDP/graphs/aa-cli
```

All GDDP graphs:

```
path:GDDP/graphs
```

Auto-generated only:

```
tag:#gddp/auto-generated
```

## Color groups

`.obsidian/graph.json` ships with starter color groups by `status` frontmatter.
Tweak in Obsidian: Settings → Graph view → Groups.

## Sign-off workflow

Set frontmatter on a node note:

```yaml
verified: verified   # unverified | verified | rejected
owned: sab           # optional — who owns review
```

Re-export preserves those fields. Syncing `verified` back to YAML is not implemented yet.