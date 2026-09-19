#!/usr/bin/env python3
"""Check a swarm.json. Every rule answers in three states: ok / finding / could-not-check.

Usage: swarm_doctor.py SWARM_JSON [--root REPO_ROOT] [--json]

A rule that never ran and a rule that came back clean must not render the same. Rules that are
declared here but not yet implemented answer `could-not-check: not implemented` — see ISSUES.md;
each one is a bounded issue for the maintainer loop to build.

Exit 1 when any rule reports a finding at level error; 0 otherwise (warnings and could-not-check
never fail the run by themselves, they are printed).
"""
from __future__ import annotations
import argparse, json, pathlib, sys
from dataclasses import dataclass, asdict

try:
    import jsonschema  # type: ignore
except ImportError:  # pragma: no cover
    jsonschema = None

HERE = pathlib.Path(__file__).resolve().parent
SCHEMA = HERE.parent / "schema" / "swarm.schema.json"


@dataclass
class Result:
    rule: str
    state: str          # ok | finding | could-not-check
    level: str          # error | warning | info
    detail: str = ""
    ref: str = ""       # edge id, agent name, path


def rule_schema(swarm: dict, root: pathlib.Path) -> list[Result]:
    """R00 — swarm.json validates against schema/swarm.schema.json."""
    if jsonschema is None:
        return [Result("R00 schema", "could-not-check", "error", "jsonschema not installed")]
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errs = sorted(jsonschema.Draft202012Validator(schema).iter_errors(swarm), key=lambda e: list(e.path))
    if not errs:
        return [Result("R00 schema", "ok", "error")]
    return [Result("R00 schema", "finding", "error", e.message, "/".join(str(p) for p in e.path)) for e in errs]


def not_implemented(rule: str, level: str):
    def _run(swarm: dict, root: pathlib.Path) -> list[Result]:
        return [Result(rule, "could-not-check", level, "not implemented")]
    _run.__doc__ = rule
    return _run


RULES = [
    rule_schema,
    not_implemented("R01 every edge names a declared agent (from, to)", "error"),
    not_implemented("R02 every agent is reachable from some flow root", "error"),
    not_implemented("R03 every handback state is referenced by a when on another edge, or the edge is terminal", "error"),
    not_implemented("R04 child authority is a subset of parent authority on every edge", "error"),
    not_implemented("R05 md exists, md_hash matches, file size <= budget_bytes", "warning"),
    not_implemented("R06 every declared script exists; every file under scripts/ is declared by some agent", "warning"),
    not_implemented("R07 two edges into one node from different parents with the same when", "warning"),
    not_implemented("R08 spawn depth from root within the harness cap (cap: measure it, do not assume)", "warning"),
    not_implemented("R09 a spawn string in an agent md names an agent with no edge from that agent", "error"),
]


def run(swarm_path: pathlib.Path, root: pathlib.Path) -> list[Result]:
    try:
        swarm = json.loads(swarm_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        return [Result("read", "could-not-check", "error", str(e), str(swarm_path))]
    out: list[Result] = []
    for rule in RULES:
        out.extend(rule(swarm, root))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("swarm", type=pathlib.Path)
    ap.add_argument("--root", type=pathlib.Path, default=pathlib.Path("."))
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    results = run(a.swarm, a.root)
    if a.json:
        print(json.dumps([asdict(r) for r in results], indent=2))
    else:
        for r in results:
            detail = f" — {r.detail}" if r.detail else ""
            ref = f" [{r.ref}]" if r.ref else ""
            print(f"{r.state:16} {r.level:8} {r.rule}{ref}{detail}")
        n_f = sum(1 for r in results if r.state == "finding")
        n_c = sum(1 for r in results if r.state == "could-not-check")
        print(f"\n{len(results)} results: {n_f} finding(s), {n_c} could-not-check")
    return 1 if any(r.state == "finding" and r.level == "error" for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
