import json, pathlib, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _run_json(swarm_name):
    out = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "swarm_doctor.py"), str(ROOT / "examples" / swarm_name), "--json"],
        capture_output=True, text=True,
    )
    assert out.stderr == "", out.stderr
    return json.loads(out.stdout)


def test_json_records_carry_explicit_edge_and_agent_fields():
    # Issue #28: the doctor's --json output must name which of "edge" or "agent" a finding
    # is about, rather than leaving a caller (the reader) to guess from the overloaded `ref`.
    results = _run_json("clean.swarm.json")
    for r in results:
        assert "edge" in r and "agent" in r, r
        # never both at once -- a record is about one edge id, or one agent name, or neither
        assert not (r["edge"] and r["agent"]), r
    # positive control: this fixture's R05 findings do carry an agent id, so a stub that always
    # returned "", "" for edge/agent (still satisfying every assertion above) would be caught here.
    assert any(r["agent"] for r in results), "expected at least one record to carry a real agent id"


def test_r04_findings_carry_an_edge_id():
    # the demonstrative example ships intentional R04 findings on purpose (ISSUES.md #4)
    results = _run_json("claude-oss.swarm.json")
    r04 = [r for r in results if r["rule"].startswith("R04") and r["state"] == "finding"]
    assert r04, "expected R04 to fire on the demonstrative example"
    assert all(r["edge"] and not r["agent"] for r in r04), r04


def test_r05_findings_carry_an_agent_name():
    results = _run_json("claude-oss.swarm.json")
    r05 = [r for r in results if r["rule"].startswith("R05") and r["state"] == "finding"]
    assert r05, "expected R05 to fire on the demonstrative example"
    assert all(r["agent"] and not r["edge"] for r in r05), r05


def test_r07_findings_carry_a_comma_joined_pair_of_edge_ids():
    results = _run_json("claude-oss.swarm.json")
    r07 = [r for r in results if r["rule"].startswith("R07") and r["state"] == "finding"]
    assert r07, "expected R07 to fire on the demonstrative example"
    for r in r07:
        assert "," in r["edge"] and not r["agent"], r
