import importlib.util, json, pathlib, subprocess, sys
import jsonschema

ROOT = pathlib.Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location("swarm_doctor", ROOT / "scripts" / "swarm_doctor.py")
swarm_doctor = importlib.util.module_from_spec(_spec)
sys.modules["swarm_doctor"] = swarm_doctor
_spec.loader.exec_module(swarm_doctor)


def _agent(**over):
    base = {
        "md": None, "md_hash": None, "summary": "x", "model": "inherit",
        "tools": [], "authority": [], "lifetime": "one-unit", "inherits": "none",
        "budget_bytes": None, "context": [], "scripts": [],
    }
    base.update(over)
    return base


def _edge(id_, from_, to_):
    return {"id": id_, "from": from_, "to": to_, "handback": []}


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
    # exit code reflects error-level findings (e.g. R04 fires on this example on purpose,
    # per ISSUES.md #4 — "ship the finding"); the CLI still prints JSON either way.
    assert out.returncode in (0, 1), out.stdout + out.stderr
    results = json.loads(out.stdout)
    states = {r["state"] for r in results}
    assert states <= {"ok", "finding", "could-not-check"}
    assert any(r["rule"].startswith("R00") and r["state"] == "ok" for r in results)


# ---- R04 — authority narrows downward -------------------------------------------------


def test_r04_fires_on_the_example_developer_sub_manager_gap():
    """Acceptance line from issue #4: developer has commit, sub-manager does not."""
    swarm = json.loads((ROOT / "examples" / "claude-oss.swarm.json").read_text(encoding="utf-8"))
    results = swarm_doctor.rule_authority_subset(swarm, ROOT)
    hits = [r for r in results if r.ref == "run.11"]
    assert len(hits) == 1
    assert hits[0].state == "finding" and hits[0].level == "error"
    assert "commit" in hits[0].detail


def test_r04_ok_when_child_authority_is_a_subset():
    swarm = {
        "agents": {
            "parent": _agent(authority=["push", "merge (gate 3 ...)"]),
            "child": _agent(authority=["merge"]),
        },
        "flows": {"f": {"root": "parent", "trigger": [], "edges": [_edge("f.01", "parent", "child")]}},
    }
    results = swarm_doctor.rule_authority_subset(swarm, ROOT)
    assert results == [swarm_doctor.Result(
        "R04 child authority is a subset of parent authority on every edge", "ok", "error")]


def test_r04_ignores_prose_string_edges_and_missing_agents():
    swarm = {
        "agents": {"parent": _agent(authority=[])},
        "flows": {"f": {"root": "parent", "trigger": [], "edges": [
            "see run: parent -> ghost",
            _edge("f.01", "parent", "ghost"),
        ]}},
    }
    results = swarm_doctor.rule_authority_subset(swarm, ROOT)
    assert results == [swarm_doctor.Result(
        "R04 child authority is a subset of parent authority on every edge", "ok", "error")]


# ---- R05 — md exists, hash matches, size within budget ---------------------------------


def test_r05_finding_when_md_missing(tmp_path):
    swarm = {"agents": {"a": _agent(md="agents/missing.md")}}
    results = swarm_doctor.rule_md_hash_budget(swarm, tmp_path)
    assert len(results) == 1
    assert results[0].state == "finding" and results[0].level == "warning"
    assert "not found" in results[0].detail


def test_r05_finding_when_hash_mismatches(tmp_path):
    (tmp_path / "agents").mkdir()
    md = tmp_path / "agents" / "a.md"
    md.write_text("hello", encoding="utf-8")
    swarm = {"agents": {"a": _agent(md="agents/a.md", md_hash="not-the-real-hash")}}
    results = swarm_doctor.rule_md_hash_budget(swarm, tmp_path)
    assert len(results) == 1
    assert "mismatch" in results[0].detail


def test_r05_finding_when_over_budget(tmp_path):
    (tmp_path / "agents").mkdir()
    md = tmp_path / "agents" / "a.md"
    md.write_text("x" * 100, encoding="utf-8")
    swarm = {"agents": {"a": _agent(md="agents/a.md", budget_bytes=10)}}
    results = swarm_doctor.rule_md_hash_budget(swarm, tmp_path)
    assert len(results) == 1
    assert "over budget_bytes" in results[0].detail


def test_r05_ok_when_hash_matches_and_within_budget(tmp_path):
    (tmp_path / "agents").mkdir()
    md = tmp_path / "agents" / "a.md"
    md.write_bytes(b"hello")
    import hashlib
    swarm = {"agents": {"a": _agent(md="agents/a.md",
                                     md_hash=hashlib.sha256(b"hello").hexdigest(),
                                     budget_bytes=1000)}}
    results = swarm_doctor.rule_md_hash_budget(swarm, tmp_path)
    assert results == [swarm_doctor.Result(
        "R05 md exists, md_hash matches, file size <= budget_bytes", "ok", "warning")]


def test_r05_write_hashes_fills_null_hashes_in_place(tmp_path):
    (tmp_path / "agents").mkdir()
    (tmp_path / "agents" / "a.md").write_bytes(b"hello")
    swarm_path = tmp_path / "swarm.json"
    swarm = {"agents": {"a": _agent(md="agents/a.md", md_hash=None)}}
    swarm_path.write_text(json.dumps(swarm), encoding="utf-8")
    n = swarm_doctor.write_missing_hashes(swarm_path, tmp_path)
    assert n == 1
    written = json.loads(swarm_path.read_text(encoding="utf-8"))
    import hashlib
    assert written["agents"]["a"]["md_hash"] == hashlib.sha256(b"hello").hexdigest()


# ---- R06 — scripts declared both ways ---------------------------------------------------


def test_r06_finding_when_declared_script_missing(tmp_path):
    swarm = {"agents": {"a": _agent(scripts=[{"name": "scripts/ghost.py", "purpose": "p", "when": "w"}])}}
    results = swarm_doctor.rule_scripts_declared(swarm, tmp_path)
    assert len(results) == 1
    assert "not found" in results[0].detail


def test_r06_finding_when_script_file_undeclared(tmp_path):
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "orphan.py").write_text("", encoding="utf-8")
    swarm = {"agents": {}}
    results = swarm_doctor.rule_scripts_declared(swarm, tmp_path)
    assert len(results) == 1
    assert "not declared by any agent" in results[0].detail


def test_r06_ok_when_declared_and_present_match_exactly(tmp_path):
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "known.py").write_text("", encoding="utf-8")
    swarm = {"agents": {"a": _agent(scripts=[{"name": "scripts/known.py", "purpose": "p", "when": "w"}])}}
    results = swarm_doctor.rule_scripts_declared(swarm, tmp_path)
    assert results == [swarm_doctor.Result(
        "R06 every declared script exists; every file under scripts/ is declared by some agent", "ok", "warning")]
