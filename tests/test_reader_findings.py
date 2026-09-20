import json, pathlib, re, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _doctor_json(swarm_path):
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "swarm_doctor.py"), str(swarm_path), "--json"],
        capture_output=True, text=True,
    )
    assert r.stderr == "", r.stderr
    return r.stdout


def test_reader_embeds_findings_payload(tmp_path):
    swarm = ROOT / "examples" / "claude-oss.swarm.json"
    findings_json = tmp_path / "findings.json"
    findings_json.write_text(_doctor_json(swarm), encoding="utf-8")
    out = tmp_path / "page.html"
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "swarm_reader.py"), str(swarm),
         "--findings", str(findings_json), "-o", str(out)],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
    page = out.read_text(encoding="utf-8")
    assert "__FINDINGS_JSON__" not in page
    assert 'id="findings"' in page
    assert "R04 child authority" in page


def test_reader_defaults_findings_to_empty_array_when_omitted(tmp_path):
    swarm = ROOT / "examples" / "claude-oss.swarm.json"
    out = tmp_path / "page.html"
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "swarm_reader.py"), str(swarm), "-o", str(out)],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
    page = out.read_text(encoding="utf-8")
    assert '<script type="application/json" id="findings">[]</script>' in page


def test_reader_refuses_invalid_findings_json(tmp_path):
    swarm = ROOT / "examples" / "claude-oss.swarm.json"
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    out = tmp_path / "page.html"
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "swarm_reader.py"), str(swarm), "--findings", str(bad), "-o", str(out)],
        capture_output=True, text=True,
    )
    assert r.returncode == 1
    assert not out.exists()


def test_reader_html_has_finding_rendering_hooks():
    # No JS test harness exists in this repo (see test_reader_embed.py) -- these are the
    # same string/regex checks that file already uses for the fetch-then-fallback shape.
    # These pin the actual filter/return logic, not just the function names, so a stub that
    # emptied out findingLegend()/findingsForNode()/findingsForEdgeId() (e.g. `return []` /
    # `return ''` unconditionally, keeping every name and string above in the source) would
    # still fail here.
    src = (ROOT / "reader" / "reader.html").read_text(encoding="utf-8")
    assert 'id="findings"' in src
    assert "could-not-check" in src  # a rule that never fired must render as such, not vanish
    assert re.search(r"function findingLegend\(\)\{", src)
    assert re.search(r"function findingsForNode\(n\)\{\s*return activeFindings\(\)\.filter\(r=>r\.agent===n\)", src)
    assert re.search(r"function findingsForEdgeId\(id\)\{", src)
    assert "if(!id) return [];" in src  # an id-less edge must not wildcard-match every finding
    assert ".split(',').includes(id)" in src
    assert "worst.set(r.rule, r)" in src  # findingLegend actually groups by rule, not a stub


def test_commands_read_runs_doctor_and_wires_findings():
    src = (ROOT / "commands" / "read.md").read_text(encoding="utf-8")
    assert "swarm_doctor.py" in src
    assert "--findings" in src
