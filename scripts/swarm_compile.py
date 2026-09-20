#!/usr/bin/env python3
"""Inject each agent's compiled contract block into its MD file, creating a skeleton first
when the file does not exist yet.

Usage: swarm_compile.py SWARM_JSON [--root REPO_ROOT] [--check]

Between `<!-- swarm:begin -->` / `<!-- swarm:end -->` in each agent's `md`, render the fixed
part described in docs/model.md's "Spawn contract": the role summary, the scripts list, and
the incoming contract (brief fields + handback states, aggregated over every edge in every
flow whose `to` is this agent). Creates the block at the top of the file, after frontmatter,
when the markers are absent. Re-running against unchanged input writes byte-identical files
(idempotent; use --check to assert that rather than write).

When `md` names a file that does not exist -- the design-helper's case, starting from
swarm.json before any agent MD has been hand-written -- that file is created: frontmatter
(`name`, `description` -- the first line of `summary`, `model`, `tools`) taken straight from
the JSON, the compiled block exactly as for an existing file, and below it one empty heading
per thing the human still has to write: what it does with the brief, one heading per declared
handback state, what it refuses. No prose under any heading -- that is the human's to write, or
the write helper's in conversation with them (docs/prior-art.md records what fabricating it
instead produces). `--check` reports a missing file as a finding and creates nothing.

An agent with `md: null` has no behaviour file by design (e.g. a pure spawner) and is skipped
silently. `harness_agents` have no `md` and are never touched. A swarm with no `agents` at all
is reported to stderr too -- schema validation is `swarm_doctor.py`'s job (R00), not this
script's, but a caller running compile first should not read a silent "0 agent(s)" as success.
Exit 1 if any agent's existing md could not be read, or (with --check) if any file would change
or be created; 0 otherwise.
"""
from __future__ import annotations
import argparse, json, pathlib, re, sys

BEGIN = "<!-- swarm:begin -->"
END = "<!-- swarm:end -->"
FRONTMATTER_RE = re.compile(r"\A---\r?\n.*?\r?\n---\r?\n", re.DOTALL)

# YAML 1.1 core-schema words a bare scalar resolves to bool/null under, and the pattern for a
# bare scalar a loader resolves to a number -- both are used only by `_yaml_scalar()`, to force
# quoting when a JSON string value would otherwise silently change type on read-back.
_YAML_RESERVED_WORDS = {"true", "false", "yes", "no", "on", "off", "null", "~", "y", "n"}
_YAML_NUMBER_RE = re.compile(r"\A[-+]?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?\Z")


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


def _first_line(text: str) -> str:
    """The first non-blank line of `text`, stripped -- used for a skeleton's `description`
    frontmatter field, derived from `summary` rather than invented."""
    for line in text.splitlines():
        line = line.strip()
        if line:
            return line
    return ""


def _yaml_scalar(value: str) -> str:
    """A YAML frontmatter scalar for `value` -- JSON-quoted (valid YAML flow scalar syntax)
    whenever a bare word would change meaning or would not round-trip as the plain string it
    is: leading/trailing space, empty, a `:`/`#`/quote, a bare YAML 1.1 boolean/null keyword
    (`yes`/`no`/`true`/`false`/`on`/`off`/`null`/`~`/`y`/`n`, any case -- a JSON string here is
    meant to stay a string, not become a loader's bool/None), a bare number (same reasoning),
    or any embedded newline -- a value spanning multiple lines could otherwise carry its own
    `---` and forge a second frontmatter delimiter, moving a later field (e.g. `tools:`) out of
    the block and into the document body."""
    special = (":", "#", '"', "'", "\n")
    if (
        value == ""
        or value != value.strip()
        or any(c in value for c in special)
        or value.lower() in _YAML_RESERVED_WORDS
        or _YAML_NUMBER_RE.match(value)
    ):
        return json.dumps(value)
    return value


def skeleton_frontmatter(name: str, agent: dict) -> str:
    """Frontmatter for a newly created md -- `name` (the catalogue key), `description` (the
    first line of `summary`), `model`, `tools` -- every value taken straight from the JSON."""
    description = _first_line((agent.get("summary") or ""))
    model = agent.get("model") or ""
    tools = agent.get("tools") or []
    lines = [
        "---",
        f"name: {_yaml_scalar(name)}",
        f"description: {_yaml_scalar(description)}",
        f"model: {_yaml_scalar(model)}",
    ]
    if tools:
        lines.append("tools:")
        lines.extend(f"  - {_yaml_scalar(t)}" for t in tools)
    else:
        lines.append("tools: []")
    lines.append("---")
    return "\n".join(lines) + "\n"


def skeleton_headings(incoming: list[dict]) -> str:
    """One empty heading per thing the human still has to write: what it does with the brief,
    one heading per declared handback state (deduplicated, first-seen order across every
    incoming edge), what it refuses. Headings only -- writing behaviour prose here is exactly
    what docs/prior-art.md records a fabricating tool doing instead."""
    states: list[str] = []
    for edge in incoming:
        for state in edge.get("handback") or []:
            if state not in states:
                states.append(state)
    lines = ["## What it does with the brief", ""]
    for state in states:
        lines.append(f"## When it hands back `{state}`")
        lines.append("")
    lines.append("## What it refuses")
    lines.append("")
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines) + "\n"


def build_skeleton(name: str, agent: dict, incoming: list[dict]) -> str:
    """The full contents of a brand-new md: frontmatter, the compiled block (identical to what
    an existing file would get), then the heading skeleton -- and nothing else."""
    frontmatter = skeleton_frontmatter(name, agent)
    block = render_block(name, agent, incoming)
    headings = skeleton_headings(incoming)
    return frontmatter + "\n" + block + "\n" + headings


def compile_swarm(swarm: dict, root: pathlib.Path, check: bool) -> tuple[list[str], list[str], list[str]]:
    """Returns (changed_paths, error_lines, created_paths). Writes/creates files unless check
    is True; a missing md is created (skeleton), never counted as an error."""
    changed: list[str] = []
    errors: list[str] = []
    created: list[str] = []
    agents = swarm.get("agents") or {}
    if not agents:
        errors.append("swarm.json has no agents to compile -- run swarm_doctor.py first")
    for name, agent in agents.items():
        md_rel = agent.get("md")
        if not md_rel:
            continue
        md_path = root / md_rel
        incoming = incoming_edges(swarm, name)
        if not md_path.is_file():
            if not check:
                # No mkdir(parents=True): an md path whose parent directory does not exist is
                # far more likely to be a typo in swarm.json than a deliberately new directory,
                # and silently fabricating a directory tree would make that typo indistinguishable
                # from the intended "no MD yet" case. Report it the same way an unreadable
                # existing file is reported instead, and process every other agent regardless.
                try:
                    skeleton = build_skeleton(name, agent, incoming)
                    with open(md_path, "w", encoding="utf-8", newline="") as f:
                        f.write(skeleton)
                except OSError as e:
                    errors.append(f"{name}: could not create {md_path}: {e}")
                    continue
            created.append(str(md_path))
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
        block = render_block(name, agent, incoming)
        new_text = inject(text, block)
        if new_text != text:
            changed.append(str(md_path))
            if not check:
                with open(md_path, "w", encoding="utf-8", newline="") as f:
                    f.write(new_text)
    return changed, errors, created


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
    changed, errors, created = compile_swarm(swarm, a.root, a.check)
    for e in errors:
        print(f"swarm_compile: {e}", file=sys.stderr)
    if a.check:
        if created:
            print("swarm_compile --check: would create:")
            for c in created:
                print(f"  {c}")
        if changed:
            print("swarm_compile --check: would change:")
            for c in changed:
                print(f"  {c}")
        if not created and not changed:
            print("swarm_compile --check: no changes")
    else:
        for c in created:
            print(f"created {c}")
        print(
            f"compiled {len(swarm.get('agents') or {})} agent(s); "
            f"{len(changed)} file(s) written, {len(created)} file(s) created"
        )
    if errors:
        return 1
    if a.check and (changed or created):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
