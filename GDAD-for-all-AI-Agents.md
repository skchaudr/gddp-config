# GDAD SYSTEM DOCTRINE & AVOIDANCE DIRECTIVES
Context: You are assisting in building the Graph-Driven Autonomous Development (GDAD) system. Your primary directive is to prioritize operational mechanics over prompt engineering.

## CORE FAILURE TO AVOID: "CONTEXT POISONING"
Agent systems fail when rules are written as documentation ideas instead of enforced as infrastructure mechanics. 
**MASTER RULE: Docs = Suggestions, Scripts = Enforcement.** Do not write polite system prompts to constrain behavior; write Python gates.

## THE 6 INFRASTRUCTURE MUST-HAVES
1. Context Gate: The agent cannot act without a loaded context payload (state, logs, priorities).
2. Decisions Log: Persistent memory (`decisions.md` or SQLite) for corrections. Do not rely on session memory for hard rules.
3. Evidence Required: "Done" means nothing without a receipt (commit hash, passing test, log output). 
4. Real Health Metrics: Cron jobs must calculate actual health (integrity vs. activity), not just ping for uptime.
5. Integrity Multiplier: High activity + broken integrity = blocked system.
6. Scripted Enforcement: If a correction happens twice, it becomes a hardcoded programmatic gate.

## THE GRAPH AS A STATE MACHINE
Do not allow agents to infer project state. The project graph (YAML) is the absolute, explicit state machine. 
Nodes only exist in strict states: `pending`, `ready`, `dispatched`, `executing`, `blocked`, `verified`, `failed`. Autonomy is strictly bounded within a single dispatched node.
