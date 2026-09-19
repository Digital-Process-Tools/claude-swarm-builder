---
description: Build the read-only page over swarm.json — map per flow, node cards with in/out, edge contracts, a step player — and publish it as an artifact or open it locally.
---

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/swarm_reader.py" swarm.json -o swarm.html
```

Then publish `swarm.html` with the Artifact tool (favicon 🐝 on first publish) or `open swarm.html`. The page carries its data; rebuild after every edit of `swarm.json`.

Reading it: click a node for its card (summary, In/Out, contract, context, scripts, spawns), click an edge for the contract between two agents, `←`/`→` to walk a flow, `Esc` for the overview. Ids (`run.11`, `U1`) are copy buttons — use them in conversation instead of "the link between X and Y".
