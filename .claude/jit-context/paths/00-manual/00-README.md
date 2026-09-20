---
title: "Declined trap.d fragments -- curate pass, 2026-09-20"
description: "Four trap.d fragments read and declined in one curate pass rather than promoted or merged, with the reason each stayed a one-off rather than a rule."
---

**`10.tracker-body-cross-contamination.md`** -- issue #10's tracker body concatenates a genuine
description with boilerplate copy-pasted across #5/#10/#11/#12. Declined: this names specific,
already-filed issue numbers on a live tracker rather than a class of future situation a jit-context
rule could fire on. A triage sweep cleaning the affected bodies directly is the right fix, not a
rule.

**`12.reader-fetch-vs-fallback-indistinguishable.md`** -- `reader/reader.html`'s fetch-then-fallback
renders identically whether the live fetch succeeded or failed silently into the embedded payload.
Declined: a product/UX gap in one file's own behavior, not a tool-call pattern or a mistake a future
agent's own actions would trigger. Better filed as an issue against `reader/reader.html` (a small
`console.info`/`console.warn` in the two `.then(init)`/`.catch` branches, per the fragment) than
absorbed as a rule.

**`4.commit-shape-implement-harden-revert.md`** -- one lane's three-commit history (implement,
harden, revert an over-fix) on #4/#5/#6, flagged as worth the maintainer seeing rather than
squashed. Declined: a one-off narrative about a single PR's shape, with no match pattern a future
call would hit. The buried actionable question -- whether `fix_commit_scope.py`'s
`needs-second-pass` threshold should treat a pure revert differently from new surface -- is a
script-design question for whoever next touches that threshold, not a jit-context rule.

**`4.r06-case-sensitivity-platform-gap.md`** -- R06's exists/declared-name comparison is
case-insensitive on one filesystem side (`Path.is_file()`) and case-sensitive on the other (string
equality), a real but already-known and already-pinned platform gap (see
`test_r06_case_mismatch_between_declared_and_disk_is_a_known_platform_gap` in
`tests/test_example_validates.py`). Declined: this is a documented code limitation with its own
red/green test as the record, not an agent-behavior trap a jit-context rule would help someone
avoid.
