---
description: Inject each agent's generated block (role summary, scripts, incoming contract) into its MD between markers.
---

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/swarm_compile.py" swarm.json --root .
```

Design is in `docs/model.md` under "Spawn contract": the fixed part compiled from the JSON is
the role summary, the scripts list and the incoming contract (brief fields + handback states,
aggregated over every edge whose `to` is that agent); the variable part — the brief — is
written by the spawner at spawn time and is never in this block. Rendered between
`<!-- swarm:begin -->` / `<!-- swarm:end -->` in each agent's `md`; created at the top after
frontmatter when the markers are absent. Idempotent — a second run against unchanged input
writes nothing; use `--check` to assert that in CI instead of writing.

Linting prose against the JSON (a spawn named in an agent's MD with no matching edge) is
tracked separately as doctor rule R09 (issue #9) — this command does not do it.
