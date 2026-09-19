import json, pathlib, re, subprocess, sys

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
    # fetch-then-fallback shape rather than executing it in a browser. That is a real limitation
    # (self-review flagged it): these string/regex checks cannot tell "the catch body genuinely
    # rehydrates from the embedded payload" from "the catch body is empty" the way running the
    # code in a browser would -- so the regexes below pin down the exact call shape (`.then(init)`,
    # `.catch(() => init(embedded))`) rather than the mere presence of `.then(`/`.catch(`, which
    # narrows but does not close that gap.
    src = (ROOT / "reader" / "reader.html").read_text(encoding="utf-8")
    assert "fetch('swarm.json')" in src or 'fetch("swarm.json")' in src
    assert 'id="tree"' in src  # the embedded payload script tag remains, as the fallback source
    assert re.search(r"\.then\(init\)", src), "the success path must actually hand data to init(), not a dead branch"
    assert re.search(r"\.catch\(\(\)\s*=>\s*init\(embedded\)\)", src), \
        "the failure path must call init(embedded), not swallow the error silently"

    # A negative assertion needs a positive control: the page must also fail loudly, not
    # silently, when a viewer interacts with it before that fetch has settled -- next()/prev()
    # (wired to buttons and arrow keys at parse time, before init() has ever run) must no-op
    # rather than throw against an undefined `flows`. A second-pass review found the Escape
    # handler was a second, separate path into overview()/draw() with no guard of its own.
    assert "function next(){ if(!flows) return;" in src
    assert "function prev(){ if(!flows) return;" in src
    assert re.search(r"key==='Escape'\)\{\s*if\(!flows\) return;", src), \
        "the Escape handler calls overview()/draw() directly and needs the same pre-init guard"

    # cost_tokens sits in the same trust-widened path as the fields esc()'d in draw() -- a
    # sibling review pass found it was the one interpolation in selectNode()'s budget line
    # left unescaped.
    assert "esc(a.cost_tokens" in src

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
