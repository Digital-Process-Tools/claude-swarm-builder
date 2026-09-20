---
description: Build the read-only page over swarm.json — map per flow, node cards with in/out, edge contracts, a step player — and publish it as an artifact or open it locally.
---

```bash
trap 'rm -f .swarm-findings.json' EXIT
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/swarm_doctor.py" swarm.json --json > .swarm-findings.json
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/swarm_reader.py" swarm.json --findings .swarm-findings.json -o swarm.html
```

Then publish `swarm.html` with the Artifact tool (favicon 🐝 on first publish) or `open swarm.html`. The page carries its data, doctor findings included; rebuild after every edit of `swarm.json`. The doctor's own exit code (1 on an error-level finding) is not a reason to skip the render — the whole point of the overlay is seeing what is broken on the picture, not only in text.

Reading it: click a node for its card (summary, In/Out, contract, context, scripts, spawns), click an edge for the contract between two agents, `←`/`→` to walk a flow, `Esc` for the overview. Ids (`run.11`, `U1`) are copy buttons — use them in conversation instead of "the link between X and Y".
