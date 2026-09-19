---
description: Write or extend swarm.json for the current repo by reading its agent MDs and declaring structure only — who spawns whom, with what, what comes back, who may do what.
---

Read `docs/model.md` first; it is the schema in prose and the line between structure (goes in the JSON) and behaviour (stays in the MD).

Then, for the repo you are in:

1. List the agent definitions (`agents/*.md`, `.claude/agents/*.md`) and the commands or skills that spawn them.
2. For each agent, fill one catalogue entry: `md`, `summary` (five lines, what it is and what it hands back), `model`, `tools`, `authority`, `lifetime`, `inherits`, `budget_bytes`, `context`, `scripts`. Read the file; do not infer from the name.
3. For each literal spawn you locate (`Agent(subagent_type: "...")`, `subagent_type:`), declare one edge with an id `<flow>.<nn>`, its `when`, `brief`, `handback`. **Search every file the parent reads, not only its own MD** — a spawn in a phase file the parent loads is that parent's edge.
4. Anything named in prose that you could not tie to a spawn goes under `declared_but_unrouted` with a `U<n>` id and the file:line. Never guess an edge.
5. Validate: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/swarm_doctor.py" swarm.json --root .`
6. Report what surprised you. Writing the tree is where the loop's stale rules show; say them by id.

Write into `swarm.json` at the repo root unless `.swarm-builder.json` names another path.
