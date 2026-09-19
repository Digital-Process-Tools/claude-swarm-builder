# The model


Vocabulary is generic on purpose. **No roles in the schema.** "root / manager / lane / auditor" are claude-oss words; another tool has other words. Roles become presets (saved property bundles) shipped beside a tree, never read by the model.

**Spec holds structure, not actions.** Control flow has two halves. _Where control goes next_ is structure — it only names nodes — and lives on edges as `when: <node>.handback == <state>`. _What gets done_ between two edges is never in the JSON: a script when it is a rule (claude-oss `tick_handback.py`), prose when it is judgment, a Workflow script when a whole phase is deterministic. The JSON may say which node and on which state; it may never say "do this". No `on` table with actions — that would need an interpreter the JSON does not have.

### Catalogue — flat list of agents, each defined once

```
agent:
  md            path to the hand-written behavior file
  md_hash       hash of that file at declaration time; reader flags a mismatch as stale
  summary       the recap card, few lines, what it is and what it hands back
  model         sonnet | opus | haiku | fable | inherit
  tools         list
  authority     list of irreversible things it may do (commit, merge, tag, publish, deploy, send)
  lifetime      one-unit | persistent
  inherits      none | summary | full    what context a parent may hand in; default none
  budget_bytes  target size of the fixed part (summary + scripts block + MD + always-context). Static, measurable without running.
  cost_tokens   measured, per run, from the cost feed. Never hand-written.
  context       files it loads into its own window: [{path, when: always | on-phase}]
  scripts       [{name, purpose, when}]
```

`context` replaces the earlier idea of a `read` edge. Reading a file is a property of the agent, not an edge: the target is a file, not an agent, and the cost lands on the reader. One edge kind only.

### Graph — edges between catalogue entries, one or more flows

```
edge:
  from, to
  count         how many spawned
  when          <node>.handback == <state> — routing only; may reference only a handback state declared on another edge, or a phase label
  terminal      true when a handback state deliberately routes nowhere (declared, so doctor does not flag it)
  isolation     none | worktree     a spawn property, so it sits here, not on the agent
  brief         schema of what the parent passes (pointers, not state)
  handback      closed set of states + payload schema
flow:
  root, trigger (cron | own-wakeup | channel-event | human), edges
```

No `on` table (state → parent's action). Routing is `when` on edges; actions are script or prose. Doctor rule that falls out: every handback state declared on an edge is either referenced by a `when` on some other edge or marked `terminal` — a state nobody routes is #1386 again.

Split catalogue from graph because the same agent sits under several parents (auditor under developer and under releaser) and several flows share one catalogue (`tick`, `release`, `doctor`). Shape is a DAG, not a tree.

### Spawn contract — what an agent starts with

Fixed, compiled from the spec, identical every spawn: (1) role summary, (2) scripts available with one line each, (3) the MD body. Variable, written by the spawner per spawn: (4) the brief, validated against the edge's schema. Brief carries pointers (issue number, worktree path), never a summary of parent state — stale the moment it is written and the child cannot tell.

### Also in the file

- `config` — the `.oss.json` slot: facts about the target, probed, referenced by key.
- `state` — what survives a run: path, schema, who writes, who reads.
- `sinks` — external systems where authority lands (GitHub, GitLab, DB, mail), drawn as boundary boxes.
- `human` — a node with no MD and infinite budget, wherever a person is still in the loop.
- Cost feed: where `cost_tokens` comes from (claude-oss `scripts/agent_cost.py`).

### Where prose stays

Most of an agent MD is behavior and paid lessons, not structure. Estimated 10–15% of `developer.md` is structure. The spec takes that slice; the rest stays hand-written and budgeted. The tool does not shrink prose, it stops prose from carrying facts that rot.
