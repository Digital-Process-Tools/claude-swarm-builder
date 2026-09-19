# Why


claude-oss runs a public repo with no human in the merge path: scheduler, sub-manager, developer lanes, auditors, releaser. It works, and Florian was lost in it: who does what, what crosses between two agents, what one tick costs, which agent may do what. The same shape exists twice more in-house (`claude-security` plugin: orchestrator → inventory → researchers → verifiers → patch-generator → patch-verifier; Jimmy on DVSI). Three hand-rolled copies, all drifting.

The structural facts (who spawns whom, with what, what comes back, what it may do, what it costs) live only in prose, in 700-line agent MDs. Nothing declares them, so nothing can check them. claude-oss #1386 is the canonical failure: the triage recorder was built, the consumer never wired, every file correct, the loop never triaged. No per-file review catches that; only a graph does.

## What we want

1. **A JSON spec** that is the single source of truth for structure. Nothing infers structure from prose; no importer greps MDs. If it is not in the JSON, it does not exist — true only once the lint in step 4 runs; until then the reader flags drift by MD hash (see catalogue).
2. **A reader**: one static page over the JSON and the MD bodies. Graph per flow, click a node → its card (role, contract, scripts, prose, cost), click an edge → the contract between two agents. Second view: walk a flow step by step so a human can say "step 6 is wrong".
3. **A compiler**, later: inject the generated block (role card, scripts, contract) into each MD between markers, so MDs stop carrying structure and cannot drift. Lint: a spawn named in prose but absent from JSON is an error.
4. **A doctor**, later: reachability from root, authority containment, nesting depth against the harness cap (**verify the cap** — "three levels" comes from a web result, not measured; agents here carry `Agent(...)` tools so nesting exists), budget vs measured, orphan scripts.
5. **An editable canvas**, last and only if the read-only view gets looked at twice. Editing is the expensive part and the commodity part.

The reader is the thing Florian was missing. Build it before anything that writes.

## What declaring claude-oss found, first evening

See `examples/claude-oss.swarm.json`, `declared_but_unrouted`: U1 and U2 are rules that outlived the step they governed (#1544); U4/U5 are undeclared handbacks; run.04 and run.06 are two paths, two triggers and two recorders for one triage sweep; `developer` is 48.5 kB against 4.5–16 kB for every other agent. None is a bug a test catches. All are the class where every file is correct and the loop is wrong.
