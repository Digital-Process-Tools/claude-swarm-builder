---
description: Co-write one agent's behaviour prose in conversation -- one agent, one heading at a time, from its compiled contract. Never batches, never fabricates a section the user has not answered.
---

Read `docs/model.md` first, specifically "Spawn contract": the compiled block is fixed,
generated from `swarm.json`; everything below it is behaviour, and behaviour is written
here, from the user, in conversation -- never invented.

Then, for `$ARGUMENTS` (the catalogue key of one agent in `swarm.json`):

1. **Read only that agent's contract.** Its `md`'s compiled block (between
   `<!-- swarm:begin -->` / `<!-- swarm:end -->`) and the incoming edges -- `from`, `brief`,
   `handback` -- whose `to` is this agent, across every flow in `swarm.json`. Not the whole
   graph, not another agent's MD: the context this needs is one contract. If the file does
   not exist yet, or has no compiled block, run
   `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/swarm_compile.py" swarm.json --root .` first and
   re-read -- never write ahead of the skeleton it produces.

2. **Ask per handback state.** For each `## When it hands back \`state\`` heading (one per
   state declared across this agent's incoming edges, deduplicated the same way the
   skeleton itself was built): when does this agent hand back this state, rather than
   another? If the user cannot describe a real condition, say so and propose removing the
   state from `swarm.json` instead of inventing one to fill the heading.

3. **Ask per authority.** For each item in this agent's `authority` list in `swarm.json`:
   the condition that must hold before it is used. For every irreversible action (commit,
   merge, tag, publish, deploy, send) the agent does *not* hold authority for: what it does
   instead -- report, stop, or hand back which state.

4. **Write what was confirmed, one section at a time.** Fill exactly the heading under
   discussion, in the user's own words, below the skeleton `swarm_compile.py` already wrote.
   Never touch the `<!-- swarm:begin -->` / `<!-- swarm:end -->` block -- it is regenerated
   from the JSON, not from this conversation. Move to the next heading only once the current
   one is answered; a heading nobody has answered yet stays empty rather than plausible.

5. **End with doctor.**
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/swarm_doctor.py" swarm.json --root .
   ```
   Read R05 (md hash / budget) and R09 (a spawn named in prose with no matching edge)
   especially -- both catch what this session just wrote into the MD.

## What it refuses

- Generating more than one agent's behaviour in a single run. One `/swarm-builder:write
  <agent>` call is one agent; a swarm with several unwritten agents needs several calls,
  each with the user present.
- Writing a heading the user has not answered. `docs/prior-art.md` records what a tool
  that fabricates agent bodies produces -- a plausible-looking prose paragraph nobody said.
  An empty heading is the honest state until the user fills it.
