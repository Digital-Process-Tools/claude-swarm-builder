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


def test_doctor_runs_and_reports_three_states(tmp_path):
    out = subprocess.run([sys.executable, str(ROOT / "scripts" / "swarm_doctor.py"), str(ROOT / "examples" / "claude-oss.swarm.json"), "--json"],
                         capture_output=True, text=True)
    assert out.returncode == 0, out.stdout + out.stderr
    results = json.loads(out.stdout)
    states = {r["state"] for r in results}
    assert states <= {"ok", "finding", "could-not-check"}
    assert any(r["rule"].startswith("R00") and r["state"] == "ok" for r in results)
