# Verification Runway - 2026-07-01

Purpose: make verification understandable enough that the next work session can move from "does the loop run?" to "do we trust the receipt?" without re-orienting.

## Current Ground Truth

- `gddp-runtime` owns verification and receipts.
- `gddp-config` owns graph truth and task contracts.
- `aa-cli` owns human dispatch/review ergonomics.
- MyAPI is a good read-only verification target because it has real handoffs, migration docs, and unclear readiness state.
- Hermes is out of this loop for now; the active surfaces are sab-air, sab-dev VM, and Mac mini as a separate available machine.

## One-Hour Pickup Path

1. Verify the config graph still validates.

   Run in VM shell:

   ```bash
   cd /home/sab/gddp-config && .venv/bin/python scripts/validate.py --project gddp-runtime
   ```

   Expected now: `0 error(s)`, with one existing warning: `return-router.yaml` unlocks future `first-overnight-run`.

2. Read the three pending verifier-hardening nodes in order.

   Run in VM shell:

   ```bash
   cd /home/sab/gddp-config && sed -n 1,220p graphs/gddp-runtime/nodes/semantic-submit-verdict-tool.yaml && sed -n 1,220p graphs/gddp-runtime/nodes/semantic-validation-retry.yaml && sed -n 1,220p graphs/gddp-runtime/nodes/verdict-confidence-split.yaml
   ```

3. Pick one execution lane.

   - Fastest useful lane: implement `semantic-submit-verdict-tool` in `gddp-runtime`.
   - If code execution is blocked: write the receipt-reading map below.
   - If GDDP gets too self-referential: run a read-only MyAPI verification inventory and turn it into a deck card or graph node.

4. Before claiming progress, write one receipt-style sentence:

   ```text
   This work makes verification more trustworthy because <specific signal now exists>, and the next human decision is <accept/retry/block/defer>.
   ```

## Verification Understanding Map

A useful verifier receipt must answer four separate questions without blending them:

| Question | Owner | Good Signal | Bad Signal |
|---|---|---|---|
| Did the code/content satisfy the acceptance criteria? | `gddp-runtime` verifier | per-criterion pass/fail with file or command evidence | vague overall score |
| Is the execution trail complete? | artifact gate | `decision.md`, `result-summary.md`, `patch.diff` present when required | implementation looks done but paper trail absent |
| Should graph truth advance? | human | evidence PR or explicit review decision | runtime mutates `project.yaml` directly |
| What should happen next? | decision loop / operator | accept, retry, block, defer, or dispatch next node | another open-ended agent chat |

Keep these separate. The live bug from handoff 014 was exactly a blended signal: criteria looked like a pass, artifacts were missing, and confidence collapsed to `0.18` even though the semantic judgment was strong.

## Stupid-Simple Productive Tasks

These are intentionally small enough to do while momentum is low.

| Task | Surface | Done When |
|---|---|---|
| Confirm graph validity | `gddp-config` | validator returns 0 errors |
| Read and choose first harness node | `gddp-config` | one node slug is named as next |
| Prepare runtime test environment | `gddp-runtime` | `python3 -m pytest -q` can run or the missing dependency is documented |
| Implement terminal `submit_verdict` | `gddp-runtime` | fake-runner tests prove terminal tool call stops the semantic loop |
| Create MyAPI readiness receipt | `myapi` / `aa-cli` | read-only inventory says what is ready, blocked, or unknown |
| Draft first overnight guard | `gddp-runtime` / docs | max dispatches, max spend, branch/PR-only rule, and morning report path are named |

## Current VM Friction

- Non-interactive SSH can reach the VM with:

  ```bash
  ssh -A -i ~/.ssh/id_ed25519_sab_mini sab@64.227.105.165
  ```

- `node` is not currently on the non-interactive SSH PATH.
- `python3` is available as Python 3.12.3.
- `gddp-runtime` test collection currently fails because `pytest` is not installed in the active Python environment.
- `gddp-config` has a working `.venv` for validation.

## Suggested Next Commit Sequence

1. `gddp-config`: keep this runway and any new graph/task contract docs together.
2. `gddp-runtime`: install/activate a local test environment, then implement only `semantic-submit-verdict-tool`.
3. `aa-cli`: make `aa verify` point at the GDDP verifier only after the verifier contract is stable enough to reuse.
4. `myapi`: use read-only verification inventories as training data for what a non-GDDP receipt should feel like.
