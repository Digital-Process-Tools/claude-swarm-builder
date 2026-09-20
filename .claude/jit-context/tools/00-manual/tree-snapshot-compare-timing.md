---
title: "tree_snapshot compare: run it right after the reviewer spawns return, before any fix commit lands on top"
description: "A compare taken after applying a review-fix commit correctly reports 'mutated', but the diff named is the lane's own fix-commit edits, not reviewer-caused -- it cannot serve as a clean receipt that the reviewer touched nothing, no matter how carefully the diff is read afterward."
tool: Bash
match: ~tree_snapshot
mode: once
---

**Run `tree_snapshot.py compare` immediately after the reviewer spawn(s) return, before applying
any review-fix commit.** A `compare` taken later -- after a fix commit for the reviewer's own
findings has already landed -- cannot be made clean after the fact: it will show "mutated" and
name exactly your own fix-commit edits, which looks identical to "the reviewer wrote something"
unless you already know the sequencing. Confirmed on #7/#8/#9 (PR #26): the reviewers held no
write tools at all, so nothing they did caused the mutation -- but the `compare` run answered a
different question than the one it was meant to answer.
