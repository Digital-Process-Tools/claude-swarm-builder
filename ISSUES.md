# Issues to file

Each one is a lane for the maintainer loop: one script, one test file, an acceptance line. File them in order; the doctor rules are independent of each other.

## 1. R01 — every edge names a declared agent
`scripts/swarm_doctor.py`: replace the `not_implemented` stub. `from` and `to` must exist in `agents` or `harness_agents`. Finding at error level, `ref` = edge id. Test: an edge to `ghost` is a finding; the example is ok.

## 2. R02 — every agent is reachable from a flow root
BFS over every flow's edges from its root. Agents in no flow = finding (error). `harness_agents` are exempt. Test: drop `run.10` from a copy of the example → `tick-dispatch` unreachable.

## 3. R03 — every handback state routes or is terminal
For each edge E with handback states S: each s in S must appear in some other edge's `when` as `<E.to>.handback == s` (string match on the state name is enough for v1), or E must be `terminal: true`. Finding (error). Test: `run.07` states `paused`/`blocked` are referenced nowhere today → this rule fires on the example; decide with the maintainer whether to add `terminal` or edges. The example ships with this finding visible, not hidden.

## 4. R04 — authority narrows downward
On every edge, `agents[to].authority ⊆ agents[from].authority`, comparing on the token before any space or parenthesis (`merge (gate 3 ...)` → `merge`). Finding (error). Test: `developer` has `commit`, `sub-manager` does not → fires on the example; the maintainer decides whether `sub-manager` should list `commit` or the rule should treat `commit` as implied by `push`. Ship the finding.

## 5. R05 — md exists, hash matches, size within budget
`md` resolves under `--root`; `md_hash` (sha256, null allowed) matches; file size ≤ `budget_bytes`. Three findings, warning level. `--write-hashes` fills null hashes in place. Test with a tmp repo.

## 6. R06 — scripts declared both ways
Every `scripts[].name` exists under `--root`; every `*.py`/`*.sh` under `scripts/` is named by at least one agent. Warning. Test with a tmp repo.

## 7. R07 — two paths for one job
Two edges into the same `to` from different `from`, whose `when` share a normalised token set above a threshold, or whose `handback` lists are identical → warning naming both ids. Test: `run.04` + `run.06` on the example.

## 8. R08 — depth within the harness cap
Longest spawn chain from any root. Cap read from `.swarm-builder.json` `depth_cap`; when absent, report `could-not-check: cap not configured — measure it` rather than assuming 3. Warning.

## 9. R09 — spawn in prose with no edge
For each agent with an `md`, search that file and every `context[].path` for `subagent_type: "<name>"` / `Agent(subagent_type`; each name located must have an edge from this agent. Error. Test: the example's `sub-manager` reads `dispatch.md`, which names `oss:triager` → matches `run.21`; remove `run.21` → fires.

## 10. CI for claude-oss
Add `swarm.json` (the example, moved) and a workflow step `swarm_doctor.py swarm.json --root .` to claude-oss. Blocked on 1–4 landing here first.

## 11. compile — inject the contract block
`scripts/swarm_compile.py`: for each agent, render summary + scripts list + incoming contract (brief fields, handback states) between `<!-- swarm:begin -->` / `<!-- swarm:end -->` in its `md`; create the block at the top after frontmatter when absent; second run zero diff. Test on a tmp copy of the example's MDs (fixtures needed, small).

## 12. reader reads a sibling file
`reader/reader.html`: when opened next to a `swarm.json` (published as a supporting file, or served locally), `fetch('swarm.json')` and use it; fall back to the embedded payload. Keeps the JSON the thing you edit.
