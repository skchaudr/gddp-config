# Pi Harness Execution Graph — Operator Intent (2026-08-07)

Sab's stated intent: Pi should be his #1 go-to agent over Codex/Claude/Droid —
well-made, maintained, capable, and the only harness with real subagent
orchestration. This graph is the audit→execute path to make that true.

Five audit areas, each paired with its complementary execution node
(audit node → execution node depends on it). Node sizing doctrine: a node ≈
one solid ~100k-token agent session of work.

1. **Pi subagents audit and config** — maximum capability, orchestration,
   reliability, traceability. Audit for weaknesses, misconfigured or
   unconfigured aspects. Propose changes to make Pi multi-agent orchestration
   a reliable, daily-reusable tool. (Known kinks already found today:
   completion-guard remote-work false positive [fixed 986d890], activity
   watchdog false positives, turn-budget resume descriptor broken, 20-turn
   default too tight for scouts, nested dispatch not available to children.)
2. **Pi TUI and interactive mode** — harness performance under heavy
   workloads; explore alternatives (my-pi-hybrid, Zed ACP, other Pi TUIs).
   Reference bar: Grok Build's TUI — never stutters, highly navigable — but
   lacks Pi's harness ability.
3. **Pi extensions audit + interactive experience** — friction sources,
   harness safety mechanisms used/not used, advisor modes, hooks and
   extensions gaps, areas to improve.
4. **Agent instructions, memory files, documentation, hook steering** — what
   exists, what's mis/un-configured, improvements. Must cite current
   consensus/research — no vibe suggestions.
5. **Pi as project/repo/portfolio piece** — Needle/Gemma/Mercury pathway?
   Pi cascade? Presentable, organized, repo clean?

Meta-note from Sab: droid's molasses pace is concerning enough that auditing
droid itself (inefficiencies, alternative execution modes) may become a
follow-up graph. The don't-own-the-lifecycle idea stands regardless.

Authoring rules when this becomes a graph: nodes via `gddp node import` only;
dependents authored `pending`; executor factory_mission once the adapter
lands; evaluation after-the-fact.
