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
import argparse, hashlib, json, pathlib, re, sys
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


_TOKEN_RE = re.compile(r"^[^\s(]+")


def _authority_tokens(entry: dict) -> set[str]:
    """The token before any space or parenthesis, e.g. "merge (gate 3 ...)" -> "merge"."""
    toks = set()
    for a in entry.get("authority", []) or []:
        m = _TOKEN_RE.match(a)
        if m:
            toks.add(m.group(0))
    return toks


def rule_authority_subset(swarm: dict, root: pathlib.Path) -> list[Result]:
    """R04 child authority is a subset of parent authority on every edge."""
    name = "R04 child authority is a subset of parent authority on every edge"
    agents: dict = {}
    agents.update(swarm.get("agents", {}) or {})
    agents.update(swarm.get("harness_agents", {}) or {})
    out: list[Result] = []
    for flow in (swarm.get("flows", {}) or {}).values():
        for edge in flow.get("edges", []) or []:
            if not isinstance(edge, dict):
                continue  # a prose string, not a declared edge
            from_name, to_name = edge.get("from"), edge.get("to")
            from_agent, to_agent = agents.get(from_name), agents.get(to_name)
            if from_agent is None or to_agent is None:
                continue  # R01's job to flag an undeclared agent
            extra = sorted(_authority_tokens(to_agent) - _authority_tokens(from_agent))
            if extra:
                out.append(Result(name, "finding", "error",
                                   f"{to_name} has authority not in {from_name}'s: {', '.join(extra)}",
                                   edge.get("id", f"{from_name}->{to_name}")))
    if not out:
        out.append(Result(name, "ok", "error"))
    return out


def _under_root(root: pathlib.Path, declared: str):
    """Resolve `declared` under `root`, refusing anything that escapes it.

    Declared paths in swarm.json are documented as repo-root-relative; an absolute path or a
    `../` climb must never let this doctor stat, read or hash a file outside --root, since
    swarm.json itself is untrusted input on an external pull request.

    Returns a ("ok", Path) / ("escapes", None) / ("error", message) triple rather than a bare
    Optional[Path], so a genuine containment violation is never reported with the same wording
    as an OSError raised while resolving (a permission error, a symlink loop) -- those are a
    could-not-check condition, not a security-relevant escape.
    """
    candidate = root / declared
    try:
        resolved = candidate.resolve()
        resolved_root = root.resolve()
    except OSError as e:
        return "error", str(e)
    if not resolved.is_relative_to(resolved_root):
        return "escapes", None
    return "ok", resolved


def rule_md_hash_budget(swarm: dict, root: pathlib.Path) -> list[Result]:
    """R05 md exists, md_hash matches, file size <= budget_bytes."""
    name = "R05 md exists, md_hash matches, file size <= budget_bytes"
    out: list[Result] = []
    for agent_name, agent in (swarm.get("agents", {}) or {}).items():
        md = agent.get("md")
        if md is None:
            continue
        status, result = _under_root(root, md)
        if status == "escapes":
            out.append(Result(name, "finding", "warning", f"md escapes --root: {md}", agent_name))
            continue
        if status == "error":
            out.append(Result(name, "finding", "warning", f"md could not be resolved: {md} ({result})", agent_name))
            continue
        path = result
        if not path.is_file():
            out.append(Result(name, "finding", "warning", f"md not found under --root: {md}", agent_name))
            continue
        data = path.read_bytes()
        declared_hash = agent.get("md_hash")
        if declared_hash is not None:
            actual_hash = hashlib.sha256(data).hexdigest()
            if declared_hash != actual_hash:
                out.append(Result(name, "finding", "warning",
                                   f"md_hash mismatch: declared {declared_hash}, actual {actual_hash}", agent_name))
        budget = agent.get("budget_bytes")
        if budget is not None and len(data) > budget:
            out.append(Result(name, "finding", "warning",
                               f"{md} is {len(data)} bytes, over budget_bytes {budget}", agent_name))
    if not out:
        out.append(Result(name, "ok", "warning"))
    return out


def write_missing_hashes(swarm_path: pathlib.Path, root: pathlib.Path) -> int:
    """Fill every null md_hash in swarm_path in place. Returns the count written."""
    swarm = json.loads(swarm_path.read_text(encoding="utf-8"))
    n = 0
    for agent in (swarm.get("agents", {}) or {}).values():
        md = agent.get("md")
        if md is None or agent.get("md_hash") is not None:
            continue
        status, result = _under_root(root, md)
        if status != "ok" or not result.is_file():
            continue
        agent["md_hash"] = hashlib.sha256(result.read_bytes()).hexdigest()
        n += 1
    if n:
        # newline="" disables universal-newline translation on write, so rewriting the file
        # to fill in hashes never flips every existing LF to the platform's own os.linesep.
        with open(swarm_path, "w", encoding="utf-8", newline="") as f:
            f.write(json.dumps(swarm, indent=2, ensure_ascii=False) + "\n")
    return n


def rule_scripts_declared(swarm: dict, root: pathlib.Path) -> list[Result]:
    """R06 every declared script exists; every file under scripts/ is declared by some agent."""
    name = "R06 every declared script exists; every file under scripts/ is declared by some agent"
    out: list[Result] = []
    declared: set[str] = set()
    for agent_name, agent in (swarm.get("agents", {}) or {}).items():
        for entry in agent.get("scripts", []) or []:
            script_name = entry.get("name")
            if script_name is None:
                continue
            declared.add(script_name)
            status, result = _under_root(root, script_name)
            if status == "escapes":
                out.append(Result(name, "finding", "warning",
                                   f"declared script escapes --root: {script_name}", agent_name))
                continue
            if status == "error":
                out.append(Result(name, "finding", "warning",
                                   f"declared script could not be resolved: {script_name} ({result})", agent_name))
                continue
            if not result.is_file():
                out.append(Result(name, "finding", "warning",
                                   f"declared script not found under --root: {script_name}", agent_name))
    scripts_dir = root / "scripts"
    if scripts_dir.is_dir():
        for p in sorted(scripts_dir.rglob("*")):
            if p.is_file() and p.suffix in (".py", ".sh"):
                rel = p.relative_to(root).as_posix()
                if rel not in declared:
                    out.append(Result(name, "finding", "warning",
                                       f"file under scripts/ is not declared by any agent: {rel}", rel))
    if not out:
        out.append(Result(name, "ok", "warning"))
    return out


def _structured_edges(swarm: dict):
    """Yield (flow_name, edge_dict) for every edge that is a dict, skipping bare-string edges."""
    for fname, flow in (swarm.get("flows") or {}).items():
        for e in (flow.get("edges") or []):
            if isinstance(e, dict):
                yield fname, e


def rule_r01(swarm: dict, root: pathlib.Path) -> list[Result]:
    """R01 every edge names a declared agent (from, to)."""
    rule = "R01 every edge names a declared agent (from, to)"
    known = set((swarm.get("agents") or {}).keys()) | set((swarm.get("harness_agents") or {}).keys())
    results = []
    for _fname, e in _structured_edges(swarm):
        eid = e.get("id", "")
        for key in ("from", "to"):
            name = e.get(key)
            if name is not None and name not in known:
                results.append(Result(rule, "finding", "error",
                                       f"{key}={name!r} is not a declared agent or harness_agent", eid))
    if not results:
        return [Result(rule, "ok", "error")]
    return results


def rule_r02(swarm: dict, root: pathlib.Path) -> list[Result]:
    """R02 every agent is reachable from some flow root."""
    rule = "R02 every agent is reachable from some flow root"
    agents = set((swarm.get("agents") or {}).keys())
    reachable: set[str] = set()
    for _fname, flow in (swarm.get("flows") or {}).items():
        root_node = flow.get("root")
        if root_node is None:
            continue
        adj: dict[str, list[str]] = {}
        for e in (flow.get("edges") or []):
            if not isinstance(e, dict):
                continue
            frm, to = e.get("from"), e.get("to")
            if frm is None or to is None:
                continue
            adj.setdefault(frm, []).append(to)
        seen = {root_node}
        stack = [root_node]
        while stack:
            node = stack.pop()
            for nxt in adj.get(node, []):
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        reachable |= seen
    missing = sorted(agents - reachable)
    if not missing:
        return [Result(rule, "ok", "error")]
    return [Result(rule, "finding", "error", "agent is not reachable from any flow root", name) for name in missing]


def rule_r03(swarm: dict, root: pathlib.Path) -> list[Result]:
    """R03 every handback state is referenced by a when on another edge, or the edge is terminal."""
    rule = "R03 every handback state is referenced by a when on another edge, or the edge is terminal"
    edges = [e for _fname, e in _structured_edges(swarm)]
    results = []
    for e in edges:
        if e.get("terminal"):
            continue
        to = e.get("to")
        handback = e.get("handback") or []
        if isinstance(handback, str):
            handback = [handback]
        for state in handback:
            needle = f"{to}.handback == {state}"
            routed = any(needle in (other.get("when") or "") for other in edges if other is not e)
            if not routed:
                results.append(Result(
                    rule, "finding", "error",
                    f"handback state {state!r} on edge to {to!r} is referenced by no other edge's when, "
                    f"and the edge is not terminal",
                    e.get("id", ""),
                ))
    if not results:
        return [Result(rule, "ok", "error")]
    return results


RULES = [
    rule_schema,
    rule_r01,
    rule_r02,
    rule_r03,
    rule_authority_subset,
    rule_md_hash_budget,
    rule_scripts_declared,
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
    ap.add_argument("--write-hashes", action="store_true",
                     help="fill every null md_hash in the swarm file in place, then run the rules")
    a = ap.parse_args(argv)
    if a.write_hashes:
        n = write_missing_hashes(a.swarm, a.root)
        if not a.json:
            print(f"wrote {n} md_hash value(s)")
    results = run(a.swarm, a.root)
    if a.json:
        print(json.dumps([asdict(r) for r in results], indent=2))
    else:
        def _oneline(s: str) -> str:
            # a swarm.json's own strings (an authority token, a path, an agent name) are
            # untrusted on an external pull request; an embedded newline in plain-text mode
            # would otherwise start a new column-0 line that looks like a second, fabricated
            # result -- collapse it to keep every result on the one line it printed on.
            return s.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")
        for r in results:
            detail = f" — {_oneline(r.detail)}" if r.detail else ""
            ref = f" [{_oneline(r.ref)}]" if r.ref else ""
            print(f"{r.state:16} {r.level:8} {_oneline(r.rule)}{ref}{detail}")
        n_f = sum(1 for r in results if r.state == "finding")
        n_c = sum(1 for r in results if r.state == "could-not-check")
        print(f"\n{len(results)} results: {n_f} finding(s), {n_c} could-not-check")
    return 1 if any(r.state == "finding" and r.level == "error" for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
