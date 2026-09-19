import json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import swarm_doctor  # noqa: E402


def _load_example():
    return json.loads((ROOT / "examples" / "claude-oss.swarm.json").read_text(encoding="utf-8"))


def _r03(swarm):
    return swarm_doctor.rule_r03(swarm, ROOT)


def test_run_07_paused_and_blocked_are_unrouted_findings_on_the_example():
    # The example ships with this finding visible, not hidden (#3): run.07's
    # `paused` and `blocked` handback states are declared but referenced by no
    # other edge's `when`, and run.07 is not terminal.
    results = _r03(_load_example())

    findings = [r for r in results if r.state == "finding" and r.ref == "run.07"]
    reported_states = {
        state
        for r in findings
        for state in ("paused", "blocked")
        if repr(state) in r.detail
    }
    assert "paused" in reported_states
    assert "blocked" in reported_states
    for r in findings:
        assert r.level == "error"
    # would this test still pass if the code did nothing? no: an unpatched stub
    # only ever returns could-not-check, never "finding".
    assert not any(r.state == "could-not-check" for r in results)


def test_terminal_edge_is_exempt_even_with_unrouted_states():
    swarm = {
        "agents": {"a": {}, "b": {}},
        "harness_agents": {},
        "flows": {
            "f": {
                "root": "a",
                "edges": [
                    {
                        "id": "f.01",
                        "from": "a",
                        "to": "b",
                        "terminal": True,
                        "handback": ["nowhere-routed"],
                    }
                ],
            }
        },
    }

    results = _r03(swarm)

    assert results == [
        swarm_doctor.Result(
            "R03 every handback state is referenced by a when on another edge, or the edge is terminal",
            "ok",
            "error",
        )
    ]


def test_plain_text_output_cannot_forge_an_extra_console_line():
    # An edge id (or any Result.ref/.detail) is content from the file being checked, not
    # something this script controls the shape of. A newline inside it must not be able to
    # fabricate a second, fake report line in the plain-text (--json-less) output. The
    # sanitizing helper (`_oneline`, landed on main via #23) is already exercised against
    # `.detail` by test_example_validates.py's own
    # test_plain_text_output_sanitizes_embedded_newlines -- this covers the same helper via
    # `.ref` instead (a forged edge id on an R01 finding), so a fix that sanitized one field
    # but not the other would still be caught.
    swarm = {
        "agents": {"a": {}, "b": {}},
        "harness_agents": {},
        "flows": {
            "f": {
                "root": "a",
                "edges": [
                    {
                        "id": "f.01\nok               error    FORGED a line that looks clean",
                        "from": "a",
                        "to": "ghost",
                    }
                ],
            }
        },
    }
    import json, pathlib as _pathlib, subprocess as _subprocess, sys as _sys
    tmp = _pathlib.Path(ROOT) / "_scratch_forge_test.json"
    tmp.write_text(json.dumps(swarm), encoding="utf-8")
    try:
        out = _subprocess.run(
            [_sys.executable, str(ROOT / "scripts" / "swarm_doctor.py"), str(tmp), "--root", str(ROOT)],
            capture_output=True, text=True,
        )
    finally:
        tmp.unlink()

    assert "FORGED" not in out.stdout.splitlines()[0]
    for line in out.stdout.splitlines():
        assert not line.strip().startswith("ok") or "FORGED" not in line


def test_routed_state_is_not_a_finding():
    swarm = {
        "agents": {"a": {}, "b": {}, "c": {}},
        "harness_agents": {},
        "flows": {
            "f": {
                "root": "a",
                "edges": [
                    {"id": "f.01", "from": "a", "to": "b", "handback": ["done"]},
                    {"id": "f.02", "from": "b", "to": "c", "when": "b.handback == done"},
                ],
            }
        },
    }

    results = _r03(swarm)

    assert results == [
        swarm_doctor.Result(
            "R03 every handback state is referenced by a when on another edge, or the edge is terminal",
            "ok",
            "error",
        )
    ]
