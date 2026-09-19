#!/usr/bin/env python3
"""Embed a swarm.json into reader/reader.html and write a standalone page.

Usage: swarm_reader.py SWARM_JSON [-o OUT_HTML]

The built page tries fetch('swarm.json') first, for the case it is published or served next
to a sibling swarm.json, and falls back to this embedded payload when that fetch fails (e.g.
opened via file://, or with no sibling present). Rebuild after every edit of swarm.json anyway —
the embedded payload is what a page opened with no sibling, or blocked from fetching, will show.
Exit 1 on unreadable or invalid JSON; never write a page over data it could not parse.
"""
from __future__ import annotations
import argparse, json, pathlib, sys

HERE = pathlib.Path(__file__).resolve().parent
TEMPLATE = HERE.parent / "reader" / "reader.html"


def build(swarm_path: pathlib.Path) -> str:
    data = json.loads(swarm_path.read_text(encoding="utf-8"))
    payload = json.dumps(data, ensure_ascii=False).replace("</script>", "<\\/script>")
    name = str(data.get("name", swarm_path.stem))
    html = TEMPLATE.read_text(encoding="utf-8")
    return (html.replace("__SWARM_JSON__", payload)
                .replace("__SWARM_TITLE__", f"{name} Swarm")
                .replace("__SWARM_NAME__", name))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("swarm", type=pathlib.Path)
    ap.add_argument("-o", "--out", type=pathlib.Path)
    a = ap.parse_args(argv)
    try:
        page = build(a.swarm)
    except (OSError, json.JSONDecodeError) as e:
        print(f"swarm_reader: could not read {a.swarm}: {e}", file=sys.stderr)
        return 1
    out = a.out or a.swarm.with_suffix(".html")
    out.write_text(page, encoding="utf-8")
    print(f"written {out} ({len(page)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
