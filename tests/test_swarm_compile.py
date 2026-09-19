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


def test_compile_creates_block_after_frontmatter(tmp_path):
    swarm_path = tmp_path / "swarm.json"
    swarm_path.write_text(json.dumps(_swarm()), encoding="utf-8")
    md = tmp_path / "worker.md"
    md.write_text("---\ndescription: a worker.\n---\n\nHand-written body.\n", encoding="utf-8")

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
    swarm_path.write_text(json.dumps(_swarm()), encoding="utf-8")
    md = tmp_path / "worker.md"
    md.write_text("---\ndescription: a worker.\n---\n\nHand-written body.\n", encoding="utf-8")

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
    swarm_path.write_text(json.dumps(_swarm()), encoding="utf-8")
    md = tmp_path / "worker.md"
    md.write_text("Hand-written body, no frontmatter.\n", encoding="utf-8")

    r = _run(swarm_path, tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    out = md.read_text(encoding="utf-8")
    assert out.startswith("<!-- swarm:begin -->")
    assert out.index("<!-- swarm:end -->") < out.index("Hand-written body, no frontmatter.")


def test_compile_skips_agent_with_null_md(tmp_path):
    swarm_path = tmp_path / "swarm.json"
    swarm_path.write_text(json.dumps(_swarm()), encoding="utf-8")
    (tmp_path / "worker.md").write_text("---\ndescription: a worker.\n---\n\nBody.\n", encoding="utf-8")

    r = _run(swarm_path, tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    assert not (tmp_path / "boss.md").exists()


def test_compile_reports_error_on_missing_md(tmp_path):
    swarm = _swarm()
    swarm["agents"]["worker"]["md"] = "missing.md"
    swarm_path = tmp_path / "swarm.json"
    swarm_path.write_text(json.dumps(swarm), encoding="utf-8")

    r = _run(swarm_path, tmp_path)
    assert r.returncode == 1
    assert "worker" in r.stderr and "missing.md" in r.stderr
