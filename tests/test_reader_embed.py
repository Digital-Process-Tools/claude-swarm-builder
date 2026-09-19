import json, pathlib, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_reader_embeds_example(tmp_path):
    out = tmp_path / "page.html"
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "swarm_reader.py"), str(ROOT / "examples" / "claude-oss.swarm.json"), "-o", str(out)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    page = out.read_text(encoding="utf-8")
    assert "__SWARM_JSON__" not in page and "__SWARM_NAME__" not in page
    assert '"sub-manager"' in page
    assert "<title>claude-oss Swarm</title>" in page


def test_reader_refuses_invalid_json(tmp_path):
    bad = tmp_path / "bad.json"; bad.write_text("{not json", encoding="utf-8")
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "swarm_reader.py"), str(bad)], capture_output=True, text=True)
    assert r.returncode == 1
    assert not bad.with_suffix(".html").exists()
