---
description: Run every rule over swarm.json and report three states per rule — ok, finding, could-not-check — never a silent skip.
---

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/swarm_doctor.py" swarm.json --root .
```

Read the output as three columns, not two. `could-not-check` is not `ok`: a rule that is not implemented yet, a file it could not read, a tool it lacked. Say which rules could not run in your report.

Exit 1 means at least one error-level finding. Fix it in `swarm.json` if the declaration was wrong, in the agent MDs if the loop was wrong — the doctor cannot tell those apart, you can.
