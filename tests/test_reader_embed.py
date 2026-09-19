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


def test_reader_fetches_sibling_swarm_json_with_embedded_fallback():
    # Issue #12: reader/reader.html should try fetch('swarm.json') first (a sibling file,
    # published or served locally) and fall back to the embedded payload when that fails.
    # No JS test harness exists in this repo, so this checks the built page's source for the
    # fetch-then-fallback shape rather than executing it in a browser.
    src = (ROOT / "reader" / "reader.html").read_text(encoding="utf-8")
    assert "fetch('swarm.json')" in src or 'fetch("swarm.json")' in src
    assert 'id="tree"' in src  # the embedded payload script tag remains, as the fallback source
    assert ".catch(" in src  # a fetch failure path exists — this is fetch-with-fallback, not fetch-or-die

    import tempfile
    with tempfile.TemporaryDirectory() as td:
        out = pathlib.Path(td) / "page.html"
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "swarm_reader.py"),
                             str(ROOT / "examples" / "claude-oss.swarm.json"), "-o", str(out)],
                            capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        page = out.read_text(encoding="utf-8")
        # the built page keeps both the fetch attempt and the embedded fallback payload
        assert "fetch('swarm.json')" in page or 'fetch("swarm.json")' in page
        assert '"sub-manager"' in page  # the embedded payload is still present as fallback data
