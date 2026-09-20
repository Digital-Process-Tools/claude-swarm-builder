---
description: Interview the user from nothing to a swarm.json -- one question at a time, restate, propose structure only, render the picture, hand off to compile.
---

This is judgment, not a script -- no command runs itself. Read `docs/model.md` first; it is
the schema in prose and the line between structure (goes in the JSON) and behaviour (stays
in the MD).

1. **Interview.** One question at a time, in the user's own domain -- never in agent names.
   Work out: what runs; what triggers it (cron, a channel event, a human); which actions are
   irreversible and who may take them; where a human must stay in the loop; what a run may
   cost. Keep asking until the graph is decidable. No agent names before that -- the
   catalogue is built afterward, from what the interview settled.

2. **Restatement.** "Here is what I think you need," in the user's own words, not yours.
   They correct it. Wrong-but-plausible is the failure to avoid, and this is the cheapest
   place to catch it -- before anything is written.

3. **Proposal.** The fewest agents that satisfy the need, as `swarm.json` -- catalogue,
   edges, contracts, authority narrowing downward. Structure only, nothing about behaviour.
   Name agents from the user's own vocabulary; the schema has no roles and neither does this
   interview. Never start from `examples/claude-oss.swarm.json` or any other preset --
   `examples/` are examples, read for shape, never copied as a template. Leave `cost_tokens`
   (measured only, never guessed) and any other field the interview did not settle absent,
   and say so rather than filling it in.

4. **Picture.** Run `/swarm-builder:read` to render `swarm.json` and publish it. Ask: "does
   this look like what you need?" Doctor findings drawn on the map (#28) are how a broken
   relation is seen fast, not only read for a minute in JSON. Loop steps 3-4 until the user
   says the picture is right.

5. **Hand off.** Once the picture is right, `/swarm-builder:compile` creates the MD
   skeletons; the `write` helper (#31) fills each one in conversation. `design` stops at
   structure -- it never writes behaviour prose itself.

Write into `swarm.json` at the repo root unless `.swarm-builder.json` names another path.
