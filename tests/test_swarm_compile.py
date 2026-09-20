import json, pathlib, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = str(ROOT / "scripts" / "swarm_compile.py")


def _swarm():
    return {
        "name": "t",
        "version": 1,
        "agents": {
            "worker": {
                "md": "worker.md",
                "md_hash": None,
                "summary": "Does the work.",
                "model": "sonnet",
                "tools": ["Bash"],
                "authority": [],
                "lifetime": "one-unit",
                "inherits": "none",
                "budget_bytes": None,
                "context": [],
                "scripts": [
                    {"name": "do.py", "purpose": "does the thing", "when": "always"}
                ],
            },
            "boss": {
                "md": None,
                "summary": "Spawns worker.",
                "model": "sonnet",
                "tools": [],
                "authority": [],
                "lifetime": "persistent",
                "inherits": "none",
                "budget_bytes": None,
                "context": [],
                "scripts": [],
            },
        },
        "flows": {
            "main": {
                "root": "boss",
                "trigger": ["cron"],
                "edges": [
                    {
                        "id": "main.01",
                        "from": "boss",
                        "to": "worker",
                        "brief": {"issue": "the issue number to fix"},
                        "handback": ["ok", "blocked"],
                    }
                ],
            }
        },
    }


def _run(swarm_path, root, extra=()):
    return subprocess.run(
        [sys.executable, SCRIPT, str(swarm_path), "--root", str(root), *extra],
        capture_output=True, text=True,
    )


def _write(path, content):
    """Write exact bytes, independent of the host platform's default text-mode line-ending
    translation -- Path.write_text(s) with no newline= (unavailable before Python 3.13 anyway)
    silently rewrites every newline in s to os.linesep on write, so a fixture meant to pin LF
    would become CRLF on a Windows test runner before the script under test ever saw it."""
    path.write_bytes(content.encode("utf-8"))


def test_compile_creates_block_after_frontmatter(tmp_path):
    swarm_path = tmp_path / "swarm.json"
    _write(swarm_path, json.dumps(_swarm()))
    md = tmp_path / "worker.md"
    _write(md, "---\ndescription: a worker.\n---\n\nHand-written body.\n")

    r = _run(swarm_path, tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr

    out = md.read_text(encoding="utf-8")
    assert out.startswith("---\ndescription: a worker.\n---\n")
    assert "<!-- swarm:begin -->" in out and "<!-- swarm:end -->" in out
    assert "Does the work." in out
    assert "`do.py` -- does the thing (always)" in out
    assert "brief.`issue` -- the issue number to fix" in out
    assert "handback: ok, blocked" in out
    assert "Hand-written body." in out
    # block sits before the hand-written body
    assert out.index("<!-- swarm:end -->") < out.index("Hand-written body.")


def test_compile_is_idempotent(tmp_path):
    swarm_path = tmp_path / "swarm.json"
    _write(swarm_path, json.dumps(_swarm()))
    md = tmp_path / "worker.md"
    _write(md, "---\ndescription: a worker.\n---\n\nHand-written body.\n")

    assert _run(swarm_path, tmp_path).returncode == 0
    first = md.read_text(encoding="utf-8")
    assert _run(swarm_path, tmp_path).returncode == 0
    second = md.read_text(encoding="utf-8")
    assert first == second

    check = _run(swarm_path, tmp_path, extra=["--check"])
    assert check.returncode == 0
    assert "no changes" in check.stdout


def test_compile_inserts_at_top_without_frontmatter(tmp_path):
    swarm_path = tmp_path / "swarm.json"
    _write(swarm_path, json.dumps(_swarm()))
    md = tmp_path / "worker.md"
    _write(md, "Hand-written body, no frontmatter.\n")

    r = _run(swarm_path, tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    out = md.read_text(encoding="utf-8")
    assert out.startswith("<!-- swarm:begin -->")
    assert out.index("<!-- swarm:end -->") < out.index("Hand-written body, no frontmatter.")


def test_compile_skips_agent_with_null_md(tmp_path):
    swarm_path = tmp_path / "swarm.json"
    _write(swarm_path, json.dumps(_swarm()))
    _write(tmp_path / "worker.md", "---\ndescription: a worker.\n---\n\nBody.\n")

    r = _run(swarm_path, tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    assert not (tmp_path / "boss.md").exists()


def test_compile_creates_skeleton_for_missing_md(tmp_path):
    swarm = _swarm()
    swarm["agents"]["worker"]["md"] = "missing.md"
    swarm_path = tmp_path / "swarm.json"
    _write(swarm_path, json.dumps(swarm))

    r = _run(swarm_path, tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "missing.md" in r.stdout

    md = tmp_path / "missing.md"
    assert md.is_file()
    out = md.read_text(encoding="utf-8")

    # frontmatter -- straight from the JSON, nothing invented
    assert out.startswith("---\n")
    assert "name: worker" in out
    assert "description: Does the work." in out
    assert "model: sonnet" in out
    assert "- Bash" in out

    # the compiled block, exactly as for an existing file
    assert "<!-- swarm:begin -->" in out and "<!-- swarm:end -->" in out
    assert "Does the work." in out
    assert "`do.py` -- does the thing (always)" in out
    assert "brief.`issue` -- the issue number to fix" in out
    assert "handback: ok, blocked" in out

    # one empty heading per declared handback state, nothing else
    assert "## When it hands back `ok`" in out
    assert "## When it hands back `blocked`" in out
    assert "## What it does with the brief" in out
    assert "## What it refuses" in out
    for heading in ("## What it does with the brief", "## When it hands back `ok`",
                    "## When it hands back `blocked`", "## What it refuses"):
        idx = out.index(heading) + len(heading)
        rest = out[idx:].lstrip("\n")
        # nothing but blank lines (or the next heading / end of file) follows -- no prose
        assert rest == "" or rest.startswith("##")


def test_compile_missing_md_idempotent_after_creation(tmp_path):
    swarm = _swarm()
    swarm["agents"]["worker"]["md"] = "missing.md"
    swarm_path = tmp_path / "swarm.json"
    _write(swarm_path, json.dumps(swarm))

    assert _run(swarm_path, tmp_path).returncode == 0
    first = (tmp_path / "missing.md").read_text(encoding="utf-8")

    r2 = _run(swarm_path, tmp_path)
    assert r2.returncode == 0
    second = (tmp_path / "missing.md").read_text(encoding="utf-8")
    assert first == second

    check = _run(swarm_path, tmp_path, extra=["--check"])
    assert check.returncode == 0
    assert "no changes" in check.stdout


def test_compile_check_reports_missing_md_without_creating(tmp_path):
    swarm = _swarm()
    swarm["agents"]["worker"]["md"] = "missing.md"
    swarm_path = tmp_path / "swarm.json"
    _write(swarm_path, json.dumps(swarm))

    r = _run(swarm_path, tmp_path, extra=["--check"])
    assert r.returncode == 1
    assert "missing.md" in r.stdout
    assert not (tmp_path / "missing.md").exists()


def test_compile_reports_error_on_no_agents(tmp_path):
    swarm_path = tmp_path / "swarm.json"
    _write(swarm_path, json.dumps({"name": "t", "version": 1, "agents": {}, "flows": {}}))

    r = _run(swarm_path, tmp_path)
    assert r.returncode == 1
    assert "no agents" in r.stderr


def test_compile_preserves_crlf_line_endings(tmp_path):
    swarm_path = tmp_path / "swarm.json"
    _write(swarm_path, json.dumps(_swarm()))
    md = tmp_path / "worker.md"
    # write raw CRLF bytes -- write_text would translate them away before the script even runs
    md.write_bytes(b"---\r\ndescription: a worker.\r\n---\r\n\r\nHand-written body.\r\n")

    r = _run(swarm_path, tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr

    raw = md.read_bytes()
    # every original CRLF line, outside the injected block, must still be CRLF -- not rewritten
    # wholesale to the host platform's line ending
    assert b"---\r\ndescription: a worker.\r\n---\r\n" in raw
    assert b"Hand-written body.\r\n" in raw
    assert b"<!-- swarm:begin -->" in raw
    # the frontmatter regex must recognize CRLF frontmatter too -- a file whose frontmatter is
    # CRLF must not fall through to the "no frontmatter" branch and get the block inserted
    # before it instead of after (this is exactly the bug a mismatched regex produces: CI ran
    # green on posix because Path.read_text's universal-newline translation silently hid it,
    # then failed on windows once read/write stopped normalizing away the real bytes)
    assert raw.index(b"---\r\ndescription") < raw.index(b"<!-- swarm:begin -->")
    assert raw.index(b"<!-- swarm:end -->") < raw.index(b"Hand-written body.")

    # idempotent under CRLF too
    r2 = _run(swarm_path, tmp_path)
    assert r2.returncode == 0
    assert md.read_bytes() == raw
