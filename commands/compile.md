---
description: Inject each agent's generated block (role card, scripts, contract) into its MD between markers, and lint prose against swarm.json. Not built yet — see ISSUES.md.
---

Not built yet. The design is in `docs/model.md` under "Spawn contract": fixed part compiled from the JSON (summary, scripts list, contract), variable part written by the spawner (the brief). Markers `<!-- swarm:begin -->` / `<!-- swarm:end -->`; idempotent; second run zero diff. Lint: a spawn named in prose with no edge in the JSON is an error.

Until it exists, say so and stop.
