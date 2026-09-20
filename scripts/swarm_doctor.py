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


_WHEN_STOPWORDS = {
    "and", "or", "not", "the", "was", "for", "are", "with", "from", "that", "this",
    "after", "before", "when", "then", "once", "during", "while", "until", "only",
    "both", "each", "same", "than", "into", "onto", "over", "under", "without",
    "within", "across", "about", "above", "below", "again", "further", "here",
    "there", "all", "any", "few", "more", "most", "other", "some", "such", "nor",
    "own", "too", "very", "can", "will", "just", "should", "now", "test", "tests",
    "pass", "fail", "passes", "fails", "run", "done", "step", "check",
}


def _when_tokens(when: str | None) -> set[str]:
    """Normalise a `when` string into a set of meaningful, comparable tokens.

    Lowercases, treats underscores the same as any other separator (so
    "command_file" and "command file" tokenize identically), and drops
    stopwords, pure-digit tokens and anything shorter than three characters --
    that last cut is deliberate: it is what keeps a shared file extension like
    ".md" or ".py" from counting as a "shared job" between two edges whose
    `when` clauses otherwise have nothing in common.
    """
    if not when:
        return set()
    raw = re.findall(r"[a-z0-9]+", when.lower().replace("_", " "))
    return {t for t in raw if len(t) >= 3 and t not in _WHEN_STOPWORDS and not t.isdigit()}


def rule_two_paths_one_job(swarm: dict, root: pathlib.Path) -> list[Result]:
    """R07 two edges into one node from different parents with the same when."""
    name = "R07 two edges into one node from different parents with the same when"
    # A shared token count of 1 is the threshold: any overlap in the normalised,
    # stopword-and-extension-filtered vocabulary of two `when` clauses feeding the
    # same node from different parents is treated as "the same job", since the
    # filtering above already removes the tokens too generic to mean that on their
    # own (see the acceptance fixture: run.04 and run.06 share only "triage").
    THRESHOLD = 1
    by_to: dict[str, list[dict]] = {}
    for flow in (swarm.get("flows", {}) or {}).values():
        for edge in flow.get("edges", []) or []:
            if not isinstance(edge, dict):
                continue  # a prose string, not a declared edge
            to_name = edge.get("to")
            if to_name is None:
                continue
            by_to.setdefault(to_name, []).append(edge)
    out: list[Result] = []
    seen_pairs: set[tuple[str, str]] = set()
    for to_name, edges in by_to.items():
        for i in range(len(edges)):
            for j in range(i + 1, len(edges)):
                a, b = edges[i], edges[j]
                if a.get("from") == b.get("from") or a.get("from") is None or b.get("from") is None:
                    continue
                a_id, b_id = a.get("id", ""), b.get("id", "")
                pair_key = tuple(sorted([a_id, b_id]))
                if pair_key in seen_pairs:
                    continue
                reason = None
                shared_tokens = _when_tokens(a.get("when")) & _when_tokens(b.get("when"))
                if len(shared_tokens) >= THRESHOLD:
                    reason = f"share when tokens: {', '.join(sorted(shared_tokens))}"
                else:
                    a_handback, b_handback = a.get("handback") or [], b.get("handback") or []
                    if a_handback and sorted(a_handback) == sorted(b_handback):
                        reason = "identical handback lists"
                if reason:
                    seen_pairs.add(pair_key)
                    out.append(Result(name, "finding", "warning",
                                       f"{a_id} and {b_id} both feed {to_name} from different parents ({reason})",
                                       f"{a_id},{b_id}"))
    if not out:
        out.append(Result(name, "ok", "warning"))
    return out


def _load_depth_cap(root: pathlib.Path):
    """Read `depth_cap` from `.swarm-builder.json` under root.

    Returns (True, cap) when a usable integer cap was found, (False, None) for every
    other case -- file absent, unreadable, not JSON, or the key missing/null. All of
    those collapse to the same "no cap configured" answer for R08's purposes: this
    doctor must never assume a default (e.g. 3) in place of a cap nobody configured.
    """
    cfg_path = root / ".swarm-builder.json"
    if not cfg_path.is_file():
        return False, None
    try:
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False, None
    cap = data.get("depth_cap") if isinstance(data, dict) else None
    # bool is a subclass of int in Python -- `"depth_cap": true` must not silently pass
    # as a cap of 1; that is a misconfiguration, not a considered value.
    if not isinstance(cap, int) or isinstance(cap, bool):
        return False, None
    return True, cap


def _longest_depth_from_root(flow: dict) -> tuple[int | None, bool]:
    """Longest spawn chain (edge count) reachable from flow["root"].

    Returns (depth, cycle_detected). A cycle makes the "longest" chain undefined
    (it is infinite), so it is reported separately rather than silently measured as
    whatever depth the recursion happened to stop at.
    """
    root_node = flow.get("root")
    if root_node is None:
        return None, False
    adj: dict[str, list[str]] = {}
    for edge in flow.get("edges", []) or []:
        if not isinstance(edge, dict):
            continue
        f, t = edge.get("from"), edge.get("to")
        if f is None or t is None:
            continue
        adj.setdefault(f, []).append(t)
    memo: dict[str, int] = {}
    visiting: set[str] = set()
    cycle = False

    def dfs(node: str) -> int:
        nonlocal cycle
        if node in memo:
            return memo[node]
        if node in visiting:
            cycle = True
            return 0
        visiting.add(node)
        best = 0
        for nxt in adj.get(node, []):
            best = max(best, 1 + dfs(nxt))
        visiting.discard(node)
        memo[node] = best
        return best

    depth = dfs(root_node)
    return depth, cycle


def rule_spawn_depth(swarm: dict, root: pathlib.Path) -> list[Result]:
    """R08 spawn depth from root within the harness cap (cap: measure it, do not assume)."""
    name = "R08 spawn depth from root within the harness cap (cap: measure it, do not assume)"
    cap_found, cap = _load_depth_cap(root)
    if not cap_found:
        return [Result(name, "could-not-check", "warning", "cap not configured — measure it")]
    out: list[Result] = []
    # One Result per flow that exceeds the cap -- not just the single deepest flow overall --
    # so a second, independently-over-cap flow is never hidden behind the worst offender.
    for flow_name, flow in (swarm.get("flows", {}) or {}).items():
        depth, cycle = _longest_depth_from_root(flow)
        if cycle:
            out.append(Result(name, "could-not-check", "warning",
                               f"flow {flow_name!r} contains a spawn cycle; depth cannot be measured", flow_name))
            continue
        if depth is None:
            continue
        if depth > cap:
            out.append(Result(name, "finding", "warning",
                               f"longest spawn chain is {depth} edge(s) from root, exceeding depth_cap {cap}",
                               flow_name))
    if not out:
        out.append(Result(name, "ok", "warning"))
    return out


_SPAWN_RE = re.compile(r'subagent_type["\']?\s*[:=]\s*["\']([^"\']+)["\']')


def rule_spawn_prose_has_edge(swarm: dict, root: pathlib.Path) -> list[Result]:
    """R09 a spawn string in an agent md names an agent with no edge from that agent."""
    name = "R09 a spawn string in an agent md names an agent with no edge from that agent"
    agents: dict = {}
    agents.update(swarm.get("agents", {}) or {})
    agents.update(swarm.get("harness_agents", {}) or {})
    edges_from: dict[str, set[str]] = {}
    for flow in (swarm.get("flows", {}) or {}).values():
        for edge in flow.get("edges", []) or []:
            if not isinstance(edge, dict):
                continue  # a prose string, not a declared edge
            f, t = edge.get("from"), edge.get("to")
            if f is None or t is None:
                continue
            edges_from.setdefault(f, set()).add(t)
    out: list[Result] = []
    for agent_name, agent in agents.items():
        declared_paths: list[str] = []
        if agent.get("md") is not None:
            declared_paths.append(agent["md"])
        for ctx in agent.get("context", []) or []:
            p = ctx.get("path") if isinstance(ctx, dict) else None
            if p is not None:
                declared_paths.append(p)
        spawned: set[str] = set()
        for declared in declared_paths:
            status, result = _under_root(root, declared)
            if status != "ok" or not result.is_file():
                # a missing or escaping declared path has nothing to scan -- genuinely absent
                # is not this rule's job to flag (R06-shaped: existence is a different rule's
                # question), and it is not the same as "present but unreadable" below.
                continue
            try:
                text = result.read_text(encoding="utf-8", errors="replace")
            except OSError as e:
                # a file that resolved and stat'd as a file but then failed to read (a
                # permission error, a symlink race, a device file) must not collapse into
                # the same "nothing spawned here" result as a file that was simply empty --
                # this doctor's whole contract is that a rule that could not look says so.
                out.append(Result(name, "could-not-check", "error",
                                   f"{declared} could not be read: {e}", agent_name))
                continue
            spawned |= set(_SPAWN_RE.findall(text))
        # a subagent_type string may carry a plugin prefix (e.g. "oss:triager") that the
        # swarm's own agent catalogue names without it ("triager"), or the other way around
        # (an edge declared to "oss:triager" while the prose spawns bare "triager") --
        # normalise both sides to their bare form before comparing, not just the spawned name.
        declared_targets = edges_from.get(agent_name, set())
        normalized_targets = declared_targets | {t.rsplit(":", 1)[-1] for t in declared_targets}
        for spawned_name in sorted(spawned):
            bare_name = spawned_name.rsplit(":", 1)[-1]
            if spawned_name in normalized_targets or bare_name in normalized_targets:
                continue
            out.append(Result(name, "finding", "error",
                               f"{agent_name}'s prose spawns {spawned_name!r} with no edge {agent_name} -> {spawned_name}",
                               agent_name))
    if not out:
        out.append(Result(name, "ok", "error"))
    return out


RULES = [
    rule_schema,
    not_implemented("R01 every edge names a declared agent (from, to)", "error"),
    not_implemented("R02 every agent is reachable from some flow root", "error"),
    not_implemented("R03 every handback state is referenced by a when on another edge, or the edge is terminal", "error"),
    rule_authority_subset,
    rule_md_hash_budget,
    rule_scripts_declared,
    rule_two_paths_one_job,
    rule_spawn_depth,
    rule_spawn_prose_has_edge,
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
