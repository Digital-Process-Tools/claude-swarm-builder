#!/usr/bin/env python3
"""Inject each agent's compiled contract block into its MD file.

Usage: swarm_compile.py SWARM_JSON [--root REPO_ROOT] [--check]

Between `<!-- swarm:begin -->` / `<!-- swarm:end -->` in each agent's `md`, render the fixed
part described in docs/model.md's "Spawn contract": the role summary, the scripts list, and
the incoming contract (brief fields + handback states, aggregated over every edge in every
flow whose `to` is this agent). Creates the block at the top of the file, after frontmatter,
when the markers are absent. Re-running against unchanged input writes byte-identical files
(idempotent; use --check to assert that rather than write).

Agents with `md: null`, or whose `md` does not resolve under --root, are skipped and reported
to stderr; the run still processes every agent it can. `harness_agents` have no `md` and are
never touched. Exit 1 if any agent's md could not be found or read, or (with --check) if any
file would change; 0 otherwise.
"""
from __future__ import annotations
import argparse, json, pathlib, re, sys

BEGIN = "<!-- swarm:begin -->"
END = "<!-- swarm:end -->"
FRONTMATTER_RE = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)


def incoming_edges(swarm: dict, name: str) -> list[dict]:
    """Every edge, across every flow, whose `to` is `name` -- string edges (bare ids) excluded."""
    out: list[dict] = []
    for flow in (swarm.get("flows") or {}).values():
        for edge in flow.get("edges") or []:
            if isinstance(edge, dict) and edge.get("to") == name:
                out.append(edge)
    return out


def render_block(name: str, agent: dict, incoming: list[dict]) -> str:
    lines = [BEGIN, "", f"### {name}", ""]
    summary = (agent.get("summary") or "").strip()
    if summary:
        lines.append(summary)
        lines.append("")
    scripts = agent.get("scripts") or []
    if scripts:
        lines.append("**Scripts**")
        for s in scripts:
            lines.append(f"- `{s['name']}` -- {s['purpose']} ({s['when']})")
        lines.append("")
    if incoming:
        lines.append("**Incoming contract**")
        for edge in incoming:
            lines.append(f"- from `{edge.get('from', '?')}` (`{edge.get('id', '?')}`)")
            brief = edge.get("brief") or {}
            for k in sorted(brief):
                lines.append(f"  - brief.`{k}` -- {brief[k]}")
            handback = edge.get("handback") or []
            if handback:
                lines.append(f"  - handback: {', '.join(handback)}")
        lines.append("")
    while lines and lines[-1] == "":
        lines.pop()
    lines.append(END)
    return "\n".join(lines) + "\n"


def inject(text: str, block: str) -> str:
    if BEGIN in text and END in text:
        start = text.index(BEGIN)
        end = text.index(END) + len(END)
        # `block` always ends in exactly one newline right after END; swallow the matching
        # newline in the old text too, or every re-run grows the file by one blank line.
        if text[end:end + 1] == "\n":
            end += 1
        return text[:start] + block + text[end:]
    m = FRONTMATTER_RE.match(text)
    if m:
        insert_at = m.end()
        rest = text[insert_at:].lstrip("\n")
        return text[:insert_at] + "\n" + block + "\n" + rest
    rest = text.lstrip("\n")
    return block + "\n" + rest


def compile_swarm(swarm: dict, root: pathlib.Path, check: bool) -> tuple[list[str], list[str]]:
    """Returns (changed_paths, error_lines). Writes files unless check is True."""
    changed: list[str] = []
    errors: list[str] = []
    for name, agent in (swarm.get("agents") or {}).items():
        md_rel = agent.get("md")
        if not md_rel:
            continue
        md_path = root / md_rel
        if not md_path.is_file():
            errors.append(f"{name}: md not found at {md_path}")
            continue
        try:
            text = md_path.read_text(encoding="utf-8")
        except OSError as e:
            errors.append(f"{name}: could not read {md_path}: {e}")
            continue
        block = render_block(name, agent, incoming_edges(swarm, name))
        new_text = inject(text, block)
        if new_text != text:
            changed.append(str(md_path))
            if not check:
                md_path.write_text(new_text, encoding="utf-8")
    return changed, errors


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("swarm", type=pathlib.Path)
    ap.add_argument("--root", type=pathlib.Path, default=pathlib.Path("."))
    ap.add_argument("--check", action="store_true", help="report what would change; write nothing")
    a = ap.parse_args(argv)
    try:
        swarm = json.loads(a.swarm.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"swarm_compile: could not read {a.swarm}: {e}", file=sys.stderr)
        return 1
    changed, errors = compile_swarm(swarm, a.root, a.check)
    for e in errors:
        print(f"swarm_compile: {e}", file=sys.stderr)
    if a.check:
        if changed:
            print("swarm_compile --check: would change:")
            for c in changed:
                print(f"  {c}")
        else:
            print("swarm_compile --check: no changes")
    else:
        print(f"compiled {len(swarm.get('agents') or {})} agent(s); {len(changed)} file(s) written")
    if errors:
        return 1
    if a.check and changed:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
