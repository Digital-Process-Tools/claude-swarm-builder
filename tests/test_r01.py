import copy, json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import swarm_doctor  # noqa: E402


def _load_example():
    return json.loads((ROOT / "examples" / "claude-oss.swarm.json").read_text(encoding="utf-8"))


def _r01(swarm):
    return swarm_doctor.rule_r01(swarm, ROOT)


def test_example_is_ok():
    results = _r01(_load_example())
    assert len(results) == 1
    assert results[0].state == "ok"
    assert results[0].level == "error"


def test_malformed_agents_shape_is_could_not_check_not_a_crash():
    # Before the shape guard, an "agents" value of the wrong JSON type (array instead of
    # object) crashed rule_r01 with an unhandled AttributeError -- would this test still pass
    # if the code did nothing? no: an unpatched rule_r01 raises here instead of returning.
    swarm = {
        "agents": ["a", "b"],
        "harness_agents": {},
        "flows": {"f": {"root": "a", "edges": [{"id": "f.01", "from": "a", "to": "b"}]}},
    }

    results = _r01(swarm)

    assert len(results) == 1
    assert results[0].state == "could-not-check"
    assert results[0].level == "error"
    assert "agents" in results[0].detail


def test_edge_with_non_string_from_is_could_not_check_not_a_crash():
    # An edge whose "from" is a JSON array (schema-invalid, but not something R00 stops R01
    # from seeing first) used to crash rule_r01 with an unhandled TypeError: unhashable type
    # 'list' the moment it reached `name not in known` -- would this test still pass if the
    # code did nothing? no: an unpatched rule_r01 raises here instead of returning.
    swarm = {
        "agents": {"a": {}, "b": {}},
        "harness_agents": {},
        "flows": {"f": {"root": "a", "edges": [{"id": "f.01", "from": ["a"], "to": "b"}]}},
    }

    results = _r01(swarm)

    assert len(results) == 1
    assert results[0].state == "could-not-check"
    assert results[0].level == "error"
    assert "not a string" in results[0].detail


def test_edge_to_ghost_is_a_finding():
    swarm = _load_example()
    # Point an existing edge's `to` at an agent that does not exist anywhere.
    edge = swarm["flows"]["run"]["edges"][0]
    assert isinstance(edge, dict)
    edge_id = edge["id"]
    edge["to"] = "ghost"

    results = _r01(swarm)

    assert any(r.state == "finding" and r.level == "error" and r.ref == edge_id for r in results)
    finding = next(r for r in results if r.ref == edge_id)
    assert "ghost" in finding.detail
    # would this test still pass if the code did nothing? no: an unpatched stub
    # only ever returns could-not-check, never "finding".
    assert not any(r.state == "could-not-check" for r in results)
