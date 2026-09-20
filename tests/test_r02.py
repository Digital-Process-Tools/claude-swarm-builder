import copy, json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import swarm_doctor  # noqa: E402


def _load_example():
    return json.loads((ROOT / "examples" / "claude-oss.swarm.json").read_text(encoding="utf-8"))


def _r02(swarm):
    return swarm_doctor.rule_r02(swarm, ROOT)


def test_example_is_ok():
    results = _r02(_load_example())
    assert len(results) == 1
    assert results[0].state == "ok"
    assert results[0].level == "error"


def test_dropping_run_10_makes_tick_dispatch_unreachable():
    swarm = _load_example()
    edges = swarm["flows"]["run"]["edges"]
    swarm["flows"]["run"]["edges"] = [
        e for e in edges if not (isinstance(e, dict) and e.get("id") == "run.10")
    ]
    # sanity: run.10 really was the only edge into tick-dispatch
    assert not any(
        isinstance(e, dict) and e.get("to") == "tick-dispatch"
        for e in swarm["flows"]["run"]["edges"]
    )

    results = _r02(swarm)

    findings = [r for r in results if r.state == "finding"]
    assert any(r.ref == "tick-dispatch" for r in findings)
    for r in findings:
        assert r.level == "error"
    # would this test still pass if the code did nothing? no: an unpatched stub
    # only ever returns could-not-check, never "finding" or "ok".
    assert not any(r.state == "could-not-check" for r in results)
