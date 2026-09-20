# claude-swarm-builder

![claude-swarm-builder — declare. read. check.](docs/swarm.png)

Declare a swarm of Claude Code agents once, in `swarm.json` — who spawns whom, with what, what comes back, who may do what irreversible, what it costs. Read it as a map. Check it on every pull request.

Structure goes in the JSON. Behaviour stays in the agent MDs, where it already is.

## Why

A loop of agents grows one issue at a time. Each fix is right in its file; nobody holds the graph. The result runs and still carries dead rules, duplicate paths and states nobody catches — the failure where every file is correct and the loop is wrong. Declaring the tree for [claude-oss](https://github.com/Digital-Process-Tools/claude-oss) found six of those in one evening, before any checker existed. `docs/why.md`.

## The verbs

| | |
|---|---|
| `/swarm-builder:design` | interview from nothing: restate, propose structure only, render, loop until the picture is right |
| `/swarm-builder:declare` | write `swarm.json` from the repo's agent MDs — structure only, never guessed |
| `/swarm-builder:read` | build the page: map per flow, node cards with in/out, edge contracts, step player |
| `/swarm-builder:doctor` | run the rules; three states per rule, `could-not-check` never reads as `ok` |
| `/swarm-builder:compile` | inject each agent's role summary, scripts list and incoming contract into its MD, idempotently -- creates a heading-only skeleton first when the MD does not exist yet |
| `/swarm-builder:write <agent>` | co-write one agent's behaviour under its skeleton's headings, in conversation, one agent at a time -- asks per handback state, per authority, writes only what you confirmed |

Linting prose against the JSON (a spawn named in an agent's MD with no matching edge) is doctor
rule R09. What is left is on the [issue tracker](https://github.com/Digital-Process-Tools/claude-swarm-builder/issues), each one a bounded issue.

## Install

```
/plugin install swarm-builder@dpt-plugins
```

Or clone and run the scripts directly — plain Python 3.9+, `jsonschema` is the one dependency.

## Building a swarm, step by step

The structure of a swarm lives in `swarm.json`; the behaviour of each agent lives in its MD. The
tool's job is to get the structure right before any behaviour is written, and to keep the two
from drifting apart afterwards. Two ways in, one loop after that. Steps marked *planned* are
filed, not shipped — the issue number says where.

**1. Install the plugin.**

```
/plugin install swarm-builder@dpt-plugins
```

**2. Get to a `swarm.json`.** Either:

- **You have agents already** — `/swarm-builder:declare`. It reads the MDs and every file they
  load, and writes structure only: one catalogue entry per agent (`md`, `summary`, `model`,
  `tools`, `authority`, `lifetime`, `budget_bytes`, `context`, `scripts`) and one edge per
  literal spawn it can locate (`from`, `to`, `when`, `brief`, `handback`). A spawn it can only
  find in prose goes under `declared_but_unrouted` with a file:line — never guessed into an
  edge. Expect this step to surprise you; writing the tree is where stale rules show.

- **You have nothing yet** — `/swarm-builder:design`. An interview, in your
  domain, not a template: what runs, what triggers it, which actions are irreversible and who
  may take them, where a human must stay in the loop, what a run may cost. It restates what it
  understood, you correct it, then it proposes the fewest agents that satisfy the need — as
  `swarm.json`, structure only, named from your words. It never starts from an example;
  `examples/` are examples.

**3. Look at it — `/swarm-builder:read`.** The page: one map per flow, a card per node with its
in/out edges, the contract on every edge, a step player. A broken relation is a thing you see in
a second here and would read for a minute in JSON. `design` ends every round on this page and
asks whether it looks like what you need; loop until it does.

![claude-oss agent tree in the reader — column is spawn depth, lighter nodes are leaves, dashed red is declared but not routed](docs/reader.png)

This is `examples/claude-oss.swarm.json` as the reader draws it: 15 agents in four columns of
spawn depth, model and budget on every card, the `Explore` node dotted because it is the harness's
and has no MD, and the dashed red edges the ones declared in prose that no spawn routes. *Planned
(#28)*: every doctor finding drawn on the map the same way — an unrouted handback state, an agent
nothing reaches, a child holding more authority than its parent — so the picture is the check,
not only the text.

**4. Refine by hand.** `swarm.json` is the file you edit from here on; `docs/model.md` is the
schema in prose. Three things only you decide:

- *Relations* — which handback state of one edge routes to which other edge (`when:
  <to>.handback == <state>`), and which states deliberately route nowhere (`terminal: true`).
- *Contracts* — what the parent passes (`brief`: pointers such as an issue number or a worktree
  path, never a summary of parent state) and the closed set of states the child hands back
  (`handback`).
- *Authority* — the irreversible things each agent may do (`commit`, `merge`, `tag`, `publish`),
  narrowing as you go down the tree.

**5. Check it — `/swarm-builder:doctor`.** Rules R01–R09, three states per rule: `ok`, a
finding, or `could-not-check`. The third is not the first. Exit 1 means an error-level finding:
fix the JSON when the declaration was wrong, the MD when the loop was wrong — the doctor cannot
tell those apart, you can.

**6. Compile — `/swarm-builder:compile`.** Injects each agent's fixed part — role summary, scripts
list, the incoming contract aggregated over every edge pointing at it — into its MD between
`<!-- swarm:begin -->` / `<!-- swarm:end -->`. Idempotent; the prose outside the markers is yours
and untouched. When the `md` does not exist yet, compile creates the skeleton — frontmatter from
the JSON, the block, one empty heading per handback state — and nothing else.

**7. Write the behaviour.** Yours to write, one agent at a time, under the skeleton's headings:
what it does with the brief, when it hands back each state, what it refuses.
`/swarm-builder:write <agent>` co-writes it with you from that agent's compiled
contract — asks per handback state, per authority, writes only what you confirmed, never a batch
of agents in one pass. Fabricated agent bodies are the failure `docs/prior-art.md` records; this
is built not to be that.

**8. Gate it in CI.** Two lines, so the declaration and the MDs cannot drift apart unnoticed:

```
python3 scripts/swarm_doctor.py swarm.json --root .
python3 scripts/swarm_compile.py swarm.json --root . --check
```

This repo runs the first against `examples/clean.swarm.json` on every pull request
(`.github/workflows/tests.yml`); its own `swarm.json` is declared the same way.

Then loop: an agent changes, `declare` extends the JSON, `read` shows what moved, `doctor` says
what broke, `compile` re-syncs the MDs.

## Swarms worth declaring

Ideas, not templates — each written along the axes the `design` interview asks about, so they
double as examples of how to think about your own. The claude-oss loop in `examples/` is one more
of these, fully worked; it is not the shape yours should take.

**Security review on every pull request** — trigger: PR opened; ~12 agents, depth 4.
A *lead* (persistent for the PR) spawns an *inventory* agent that partitions the diff into
components and hands back the list. Per component, a *researcher* (worktree isolation, read-only)
hunts for candidate findings across a threat model the lead wrote from the inventory; each hands
back `findings[] | nothing-found | could-not-read`. Per candidate, three *verifiers* in parallel
argue *against* it — exploitability, reachability, whether a control already covers it — each
handing back `confirmed | refuted | could-not-tell`; a *tally* script, not an agent, decides what
survives. Per survivor, a *patch-writer* in its own worktree, then a *patch-verifier* that runs the
tests and says `safe | breaks | could-not-run`. A *reporter* posts one comment. Authority: the
reporter may `comment`; nobody may `push`, `merge` or `close`. A human merges. What declaring it
shows first: the edge from verifier to tally has three states and the lead's prose only ever
routed two.

**Dependency updates** — trigger: a bot's PR; ~8 agents, depth 3.
A *triager* reads the PR and classifies `patch | minor | major | unknown`. `patch` and `minor` go
to a *changelog-reader* (what changed upstream, hands back `benign | behavioural | breaking |
no-changelog`) and, in parallel, a *test-runner* with worktree isolation (`green | red |
could-not-run`). Both green and benign route to a *merger* holding `merge` — the only agent with
it — else to an *investigator* that bisects the failure and files an issue with authority
`open-issue`. `major` and `unknown` route to a *human* node, always; a *summariser* writes what
the human will read. A *sink* box for GitHub. The edge that matters is triager → merger: it does
not exist, and the picture makes that absence visible.

**Documentation drift** — trigger: merge to main; ~9 agents, depth 3.
A *surface-differ* (script-heavy: public API, CLI flags, config keys) hands back the delta. Per
changed surface, a *doc-locator* finds every page that mentions it — `found[] | none |
could-not-search` — and a *gap-filer* opens one issue per gap. Per issue, a *writer* lane in a
worktree drafts the change and opens a PR; a *reviewer* checks the draft against the code, not
the old docs, and hands back `accurate | wrong | could-not-verify`; a *linker* adds the
cross-references. Authority stops at `open PR` everywhere; a human merges docs too. Declaring it
exposes how many writers a single merge can fan out to, and that is the `count` field on one
edge, so the budget becomes a number.

**Incident first response** — trigger: an alert on a channel; ~10 agents, depth 3.
A *responder* (persistent for the incident) spawns a *log-reader* and a *metrics-reader* in
parallel, each handing back `window | nothing-in-window | could-not-read`. From those, the
responder writes three or four hypotheses and spawns one *hypothesis lane* each, in parallel,
every lane handing back `supported | refuted | need-data` with the evidence it read. `need-data`
routes to a *data-fetcher* with read access to production; nothing else has it. A *scribe*
drafts the timeline as the lanes report; a *comms-drafter* writes the status-page text the human
will post. No agent holds `deploy`, `rollback` or `post` — the on-call human does. What the
picture shows: the responder's `inherits: full` edge to the scribe is the one place where the
whole context is handed down, so it is the one to budget.

**Support inbox** — trigger: new ticket; ~8 agents, depth 3.
A *classifier* hands back one of `question | bug | account | billing | abuse | unclear` — that
handback is the routing table for the whole swarm, so it is the contract to get right first.
`question` goes to an *answerer* with read access to the docs and the product, then to a
*fact-checker* that re-derives every claim (`holds | wrong | could-not-check`); `bug` to a
*reproducer* in a sandbox that hands back `reproduced | could-not-reproduce | need-info` and a
*filer* with `open-issue`; `account` and `billing` to a *lookup* agent with read access to the
customer record and nothing else; `abuse` and `unclear` straight to a *human*. One *sender* node
holds `send` and is a human until the fact-checker's `wrong` rate is measured low enough to
change that — and the JSON is where that decision is recorded when it is made.

**Nightly data quality** — trigger: cron; ~10 agents, depth 2.
A *scheduler* spawns one *checker* per table, in parallel, each with a `budget_bytes` small
enough that twenty of them cost less than one investigator: `clean | anomalies[] |
could-not-query`. Anomalies route to an *investigator* per table that reads the pipeline for
that table and hands back `upstream-cause | data-cause | could-not-tell`; each cause routes to a
*filer* with `open-issue`, and `could-not-tell` to a *human*. A *reporter* writes the morning
digest. What declaring it exposes, every time: the checkers whose `could-not-query` state nobody
routes — the failure where the check did not run and the digest said "clean".

Each of these is a `swarm.json` of eight to twelve agents. The point of declaring one before
writing it is the same every time: the contract between two agents is decided on the picture,
not discovered in production — and the three-state handback (`ok | finding | could-not`) is on
every edge, because an agent that could not do its job must never look like one that found
nothing.

## The model, in one screen

```
agent:  md · summary · model · tools · authority · lifetime · inherits · budget_bytes · cost_tokens · context[] · scripts[]
edge:   id · from · to · count · when · terminal · isolation · brief{} · handback[]
flow:   root · trigger[] · edges[]
```

No roles in the schema — `lane`, `auditor`, `manager` are presets copied from an example, never read by the model. No actions on edges: `when` routes, it never says "do this"; what gets done is a script when it is a rule and prose when it is judgment. `docs/model.md`.

## Worked example

`examples/claude-oss.swarm.json` — 15 agents, 21 edges, and the six things declaring it exposed under `declared_but_unrouted`. `python3 scripts/swarm_reader.py examples/claude-oss.swarm.json` renders it. The built page always tries `fetch('swarm.json')` first, so it only picks up a sibling when one is served under exactly that literal name — this worked example is built from `claude-oss.swarm.json`, so opening its rendered page exercises the embedded-payload fallback, not the live fetch, unless you also save the JSON alongside it as `swarm.json`. Either way the JSON stays the thing you edit.

Pass `python3 scripts/swarm_doctor.py examples/claude-oss.swarm.json --json` to `swarm_reader.py --findings` and every rule's outcome — not just `declared_but_unrouted` — is drawn on the same page: coloured nodes and edges by level, a legend entry per rule that fired, `could-not-check` rules named as such rather than silently missing, and the finding text on click. `commands/read.md` (`/oss:read`) already wires this in.

## Prior art

Three canvases (claude-studio, ccbuilder, AgenTopology) and one description format (Swarm Skills) exist. None declares edges as data for MD-defined agents, checks authority on an edge, joins measured cost to a design, or round-trips hand-written prose. AgenTopology was tried on claude-oss: its import dropped every MD body and fabricated an alphabetical flow that then "passed all validation rules". `docs/prior-art.md`.

## License

Community License — free to use, copy and modify for personal, educational and internal business purposes; no commercial redistribution. See `LICENSE`.
