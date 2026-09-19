#!/usr/bin/env python3
"""Inject each agent's compiled contract block into its MD file.

Usage: swarm_compile.py SWARM_JSON [--root REPO_ROOT] [--check]

Between `<!-- swarm:begin -->` / `<!-- swarm:end -->` in each agent's `md`, render the fixed
part described in docs/model.md's "Spawn contract": the role summary, the scripts list, and
the incoming contract (brief fields + handback states, aggregated over every edge in every
flow whose `to` is this agent). Creates the block at the top of the file, after frontmatter,
when the markers are absent. Re-running against unchanged input writes byte-identical files
(idempotent; use --check to assert that rather than write).

An agent with `md: null` has no behaviour file by design (e.g. a pure spawner) and is skipped
silently; an agent whose `md` does not resolve under --root is a real problem and is reported to
stderr, with the run still processing every agent it can. `harness_agents` have no `md` and are
never touched. A swarm with no `agents` at all is reported to stderr too -- schema validation is
`swarm_doctor.py`'s job (R00), not this script's, but a caller running compile first should not
read a silent "0 agent(s)" as success. Exit 1 if any agent's md could not be found or read, or
(with --check) if any file would change; 0 otherwise.
"""
from __future__ import annotations
import argparse, json, pathlib, re, sys

BEGIN = "<!-- swarm:begin -->"
END = "<!-- swarm:end -->"
FRONTMATTER_RE = re.compile(r"\A---\r?\n.*?\r?\n---\r?\n", re.DOTALL)


def _eol(text: str) -> str:
    """The line ending already in use in `text` -- CRLF if any CRLF appears, else LF.

    `render_block()` always builds its block with plain '\n'; every newline this module writes
    into a file is passed through this so the block matches the surrounding file's own convention
    instead of introducing a second, mixed line-ending style alongside whatever the read side
    preserved."""
    return "\r\n" if "\r\n" in text else "\n"


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
    eol = _eol(text)
    if eol != "\n":
        block = block.replace("\n", eol)

    def _strip_leading_eols(s: str) -> str:
        while s.startswith(eol):
            s = s[len(eol):]
        return s

    if BEGIN in text and END in text:
        start = text.index(BEGIN)
        end = text.index(END) + len(END)
        # `block` always ends in exactly one eol right after END; swallow the matching eol in
        # the old text too, or every re-run grows the file by one blank line.
        if text[end:end + len(eol)] == eol:
            end += len(eol)
        return text[:start] + block + text[end:]
    m = FRONTMATTER_RE.match(text)
    if m:
        insert_at = m.end()
        rest = _strip_leading_eols(text[insert_at:])
        return text[:insert_at] + eol + block + eol + rest
    rest = _strip_leading_eols(text)
    return block + eol + rest


def compile_swarm(swarm: dict, root: pathlib.Path, check: bool) -> tuple[list[str], list[str]]:
    """Returns (changed_paths, error_lines). Writes files unless check is True."""
    changed: list[str] = []
    errors: list[str] = []
    agents = swarm.get("agents") or {}
    if not agents:
        errors.append("swarm.json has no agents to compile -- run swarm_doctor.py first")
    for name, agent in agents.items():
        md_rel = agent.get("md")
        if not md_rel:
            continue
        md_path = root / md_rel
        if not md_path.is_file():
            errors.append(f"{name}: md not found at {md_path}")
            continue
        try:
            # newline="": no universal-newline translation, so a file's existing line endings
            # pass through untouched instead of the whole file being rewritten to the host OS's
            # os.linesep (LF -> CRLF on every line on Windows -- and CRLF -> LF on *every*
            # platform on the read side, without this). Path.read_text/write_text only grew a
            # newline= parameter in Python 3.13; this repo's CI runs 3.9 and 3.12, so the plain
            # open() form is used instead -- it has carried newline= since Python 3.0.
            with open(md_path, encoding="utf-8", newline="") as f:
                text = f.read()
        except OSError as e:
            errors.append(f"{name}: could not read {md_path}: {e}")
            continue
        block = render_block(name, agent, incoming_edges(swarm, name))
        new_text = inject(text, block)
        if new_text != text:
            changed.append(str(md_path))
            if not check:
                with open(md_path, "w", encoding="utf-8", newline="") as f:
                    f.write(new_text)
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
