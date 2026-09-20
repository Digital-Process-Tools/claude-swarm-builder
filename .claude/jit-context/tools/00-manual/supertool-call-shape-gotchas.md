---
title: "supertool call shape: backslash counts, colon-form message collisions, grep LIMIT=0, and cwd for outside-tree reads"
description: "Four recovered supertool refusals from one lane (#7/#8/#9, PR #26), one round-trip each: edit:@- backslash-count confusion, git-commit colon-form breaking on a literal ':::' in the message, grep LIMIT=0 refused rather than read as unlimited, and reading outside the current worktree needing an explicit cwd: op first."
tool: Bash
match: ~\./?supertool
mode: once
---

**`edit:@-`'s `literal_backslashes = true` exempts the *refusal*, not the byte count.** A TOML
literal block never processes escapes -- whatever backslash count you type is what lands on
disk. The trap: typing the *Python-source* count (already doubled once for the escape in the
.py file) instead of the count Python's own parser sees after unescaping. Fix: generate the
payload with a throwaway `python3 -c` that only **prints** (never writes, to avoid the separate
heredoc-write guard) using string multiplication of a single-backslash literal, then pipe that
straight into `edit:@-`. Typing the sequence by hand cost three failed round-trips on one
function.

**`git-commit:::MESSAGE:::PATHS` (colon-form) refuses when the message itself contains the
literal `:::` separator.** Use `git-commit:@-` with a TOML `message`/`paths` payload instead.

**`grep:PATTERN:PATH:LIMIT` refuses `LIMIT=0`** -- it is not read as "unlimited". Pass an
actual number.

**Reading a path outside the current worktree (e.g. a plugin cache path) needs `cwd:PLUGIN_ROOT`
as its own, *first* op in the call, before `read:relative/path`.** `read:cwd:PATH:file` as one
compound op is not real syntax and errors. Confirmed again during this curate pass itself,
reading `commands/run/curate.md` out of the plugin cache.
