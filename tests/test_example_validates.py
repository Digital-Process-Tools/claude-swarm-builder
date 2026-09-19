import json, pathlib, subprocess, sys
import jsonschema

ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_claude_oss_example_matches_schema():
    schema = json.loads((ROOT / "schema" / "swarm.schema.json").read_text(encoding="utf-8"))
    swarm = json.loads((ROOT / "examples" / "claude-oss.swarm.json").read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(swarm)


def test_own_swarm_matches_schema():
    schema = json.loads((ROOT / "schema" / "swarm.schema.json").read_text(encoding="utf-8"))
    swarm = json.loads((ROOT / "swarm.json").read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(swarm)


def test_clean_example_matches_schema():
    # examples/clean.swarm.json is the CI gate's own fixture (issue #20): built to stay
    # R01-R03-clean once those rules stop being stubs, so the gate is not the demonstrative
    # example, which ships its R03 finding on purpose (issue #3).
    schema = json.loads((ROOT / "schema" / "swarm.schema.json").read_text(encoding="utf-8"))
    swarm = json.loads((ROOT / "examples" / "clean.swarm.json").read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(swarm)


def test_clean_example_has_no_ghost_edges():
    # Stands in for R01 while it is still a not_implemented stub (#1): every edge's
    # from/to names a declared agent. A fixture meant to gate CI on R01 must not itself
    # depend on the stub to look clean.
    swarm = json.loads((ROOT / "examples" / "clean.swarm.json").read_text(encoding="utf-8"))
    declared = set(swarm.get("agents", {})) | set(swarm.get("harness_agents", {}))
    for flow in swarm["flows"].values():
        for edge in flow["edges"]:
            if isinstance(edge, str):
                continue
            assert edge["from"] in declared, edge["id"]
            assert edge["to"] in declared, edge["id"]


def test_clean_example_every_agent_reachable():
    # Stands in for R02 (#2) the same way: BFS from each flow's root must reach every
    # declared agent, so the fixture does not go stale once R02 stops being a stub.
    swarm = json.loads((ROOT / "examples" / "clean.swarm.json").read_text(encoding="utf-8"))
    reachable = set()
    for flow in swarm["flows"].values():
        frontier = [flow["root"]]
        reachable.add(flow["root"])
        while frontier:
            node = frontier.pop()
            for edge in flow["edges"]:
                if isinstance(edge, str):
                    continue
                if edge["from"] == node and edge["to"] not in reachable:
                    reachable.add(edge["to"])
                    frontier.append(edge["to"])
    assert reachable == set(swarm["agents"])


def test_clean_example_every_handback_state_routes_or_terminal():
    # Stands in for R03 (#3): every state in a non-terminal edge's handback list must be
    # referenced by some other edge's `when` as "<to>.handback == <state>".
    swarm = json.loads((ROOT / "examples" / "clean.swarm.json").read_text(encoding="utf-8"))
    edges = [e for flow in swarm["flows"].values() for e in flow["edges"] if not isinstance(e, str)]
    whens = " ".join(e.get("when", "") for e in edges)
    for edge in edges:
        if edge.get("terminal"):
            continue
        for state in edge["handback"]:
            needle = f"{edge['to']}.handback == {state}"
            assert needle in whens, f"{edge['id']}: {state} routes nowhere and edge is not terminal"


def test_doctor_runs_and_reports_three_states(tmp_path):
    # Points at the CI gate's own fixture (examples/clean.swarm.json, issue #20), not the
    # demonstrative example, which ships an intentional R03 finding once that rule is real.
    out = subprocess.run([sys.executable, str(ROOT / "scripts" / "swarm_doctor.py"), str(ROOT / "examples" / "clean.swarm.json"), "--json"],
                         capture_output=True, text=True)
    assert out.returncode == 0, out.stdout + out.stderr
    results = json.loads(out.stdout)
    states = {r["state"] for r in results}
    assert states <= {"ok", "finding", "could-not-check"}
    assert any(r["rule"].startswith("R00") and r["state"] == "ok" for r in results)
