---
title: "review_return.py --framed: could-not-classify against an oss:auditor return is a known shape mismatch, not real ambiguity"
description: "review_return.py's --framed classifier reads Explore's sentinel-formatted return fine but returns could-not-classify (exit 5) for oss:auditor's per-checklist-class report -- a structural mismatch between the classifier and this agent's own convention, confirmed during #7/#8/#9 (PR #26)."
tool: Bash
match: ~review_return\.py
mode: once
---

**A `could-not-classify` (exit 5) from `review_return.py --framed` against an `oss:auditor`
return is not real ambiguity -- it is this specific pairing hitting a known classifier gap.**
Do not treat the verdict as inconclusive and re-run or escalate; hand-read `oss:auditor`'s own
return directly instead, the same way its brief already documents its report shape.

This will apparently recur for **any** Explore + `oss:auditor` pairing fed to the same
classifier, until either the classifier learns `oss:auditor`'s shape or the auditor's brief is
taught the classifier's sentinel convention -- neither has happened yet.
