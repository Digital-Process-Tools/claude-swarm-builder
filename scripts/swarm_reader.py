#!/usr/bin/env python3
"""Embed a swarm.json (and optionally a doctor --json findings file) into reader/reader.html.

Usage: swarm_reader.py SWARM_JSON [-o OUT_HTML] [--findings FINDINGS_JSON]

The built page tries fetch('swarm.json') first, for the case it is published or served next
to a sibling swarm.json, and falls back to this embedded payload when that fetch fails (e.g.
opened via file://, or with no sibling present). Rebuild after every edit of swarm.json anyway —
the embedded payload is what a page opened with no sibling, or blocked from fetching, will show.

--findings PATH embeds swarm_doctor.py's --json output next to the swarm payload, so the page
can colour findings onto the map instead of only showing declared_but_unrouted edges. Omitted,
it embeds an empty array — the page must never treat "no findings file was passed" the same as
a script error, so a caller that forgets the flag gets a plain, findings-free page rather than
a crash.

Exit 1 on unreadable or invalid JSON (either file); never write a page over data it could not
parse.
"""
from __future__ import annotations
import argparse, json, pathlib, sys

HERE = pathlib.Path(__file__).resolve().parent
TEMPLATE = HERE.parent / "reader" / "reader.html"


def build(swarm_path: pathlib.Path, findings_path: pathlib.Path | None = None) -> str:
    data = json.loads(swarm_path.read_text(encoding="utf-8"))
    payload = json.dumps(data, ensure_ascii=False).replace("</script>", "<\\/script>")
    name = str(data.get("name", swarm_path.stem))
    if findings_path is not None:
        findings = json.loads(findings_path.read_text(encoding="utf-8"))
    else:
        findings = []
    findings_payload = json.dumps(findings, ensure_ascii=False).replace("</script>", "<\\/script>")
    html = TEMPLATE.read_text(encoding="utf-8")
    return (html.replace("__SWARM_JSON__", payload)
                .replace("__FINDINGS_JSON__", findings_payload)
                .replace("__SWARM_TITLE__", f"{name} Swarm")
                .replace("__SWARM_NAME__", name))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("swarm", type=pathlib.Path)
    ap.add_argument("-o", "--out", type=pathlib.Path)
    ap.add_argument("--findings", type=pathlib.Path, default=None,
                     help="swarm_doctor.py --json output to embed and overlay on the map")
    a = ap.parse_args(argv)
    try:
        page = build(a.swarm, a.findings)
    except (OSError, json.JSONDecodeError) as e:
        bad = a.swarm
        try:
            json.loads(a.swarm.read_text(encoding="utf-8"))
            if a.findings is not None:
                bad = a.findings
        except (OSError, json.JSONDecodeError):
            bad = a.swarm
        print(f"swarm_reader: could not read {bad}: {e}", file=sys.stderr)
        return 1
    out = a.out or a.swarm.with_suffix(".html")
    out.write_text(page, encoding="utf-8")
    print(f"written {out} ({len(page)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
