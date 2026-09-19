import importlib.util, json, pathlib, subprocess, sys
import jsonschema
import pytest

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
    # per ISSUES.md #4 — "ship the finding"); the CLI still prints JSON either way. stderr
    # empty is what actually distinguishes "ran and found errors" from "crashed" here --
    # an uncaught exception also exits 1 in plain Python, so returncode alone cannot tell them apart.
    assert out.returncode in (0, 1), out.stdout + out.stderr
    assert out.stderr == "", out.stderr
    results = json.loads(out.stdout)
    states = {r["state"] for r in results}
    assert states <= {"ok", "finding", "could-not-check"}
    assert any(r["rule"].startswith("R00") and r["state"] == "ok" for r in results)
    assert any(r["rule"].startswith("R01") and r["state"] == "ok" for r in results)
    assert any(r["rule"].startswith("R02") and r["state"] == "ok" for r in results)


def test_r04_fires_broadly_on_the_example_not_just_once():
    # the shipped example's authority is structured with disjoint scopes per role (scheduler
    # vs. sub-manager vs. releaser etc.), so R04 is expected to fire on many edges, not the
    # single developer/sub-manager gap the issue's acceptance line calls out by name.
    swarm = json.loads((ROOT / "examples" / "claude-oss.swarm.json").read_text(encoding="utf-8"))
    results = swarm_doctor.rule_authority_subset(swarm, ROOT)
    findings = [r for r in results if r.state == "finding"]
    assert len(findings) > 1
    assert all(r.level == "error" for r in findings)


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
    # covers both directions of "an edge names an undeclared agent" (R01's job to flag it,
    # not R04's): a missing "to" and a missing "from". A defaulting bug -- treating a missing
    # agent as one with empty authority instead of skipping the edge -- would still pass this
    # for the missing-"to" case (nothing to compare against) but would wrongly fire a finding
    # for the missing-"from" case, since child's real authority would then look like "extra".
    swarm = {
        "agents": {
            "parent": _agent(authority=[]),
            "child": _agent(authority=["commit"]),
        },
        "flows": {"f": {"root": "parent", "trigger": [], "edges": [
            "see run: parent -> ghost",
            _edge("f.01", "parent", "ghost"),
            _edge("f.02", "ghost", "child"),
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


def test_r05_write_hashes_preserves_line_endings(tmp_path):
    (tmp_path / "agents").mkdir()
    (tmp_path / "agents" / "a.md").write_bytes(b"hello")
    swarm_path = tmp_path / "swarm.json"
    swarm = {"agents": {"a": _agent(md="agents/a.md", md_hash=None)}}
    with open(swarm_path, "w", encoding="utf-8", newline="") as f:
        f.write(json.dumps(swarm))
    swarm_doctor.write_missing_hashes(swarm_path, tmp_path)
    raw = swarm_path.read_bytes()
    assert b"\r\n" not in raw


def test_r05_finding_when_md_escapes_root_absolute(tmp_path):
    outside = tmp_path.parent / "not_under_root_secret.txt"
    outside.write_bytes(b"x" * 34)
    swarm = {"agents": {"a": _agent(md=str(outside), budget_bytes=5)}}
    results = swarm_doctor.rule_md_hash_budget(swarm, tmp_path)
    assert len(results) == 1
    assert "escapes --root" in results[0].detail
    assert "34 bytes" not in results[0].detail


def test_r05_finding_when_md_escapes_root_dotdot(tmp_path):
    swarm = {"agents": {"a": _agent(md="../outside.md")}}
    results = swarm_doctor.rule_md_hash_budget(swarm, tmp_path)
    assert len(results) == 1
    assert "escapes --root" in results[0].detail


def test_write_missing_hashes_refuses_to_hash_outside_root(tmp_path):
    outside = tmp_path.parent / "outside_hash_target.md"
    outside.write_bytes(b"secret")
    swarm_path = tmp_path / "swarm.json"
    swarm = {"agents": {"a": _agent(md=str(outside), md_hash=None)}}
    swarm_path.write_text(json.dumps(swarm), encoding="utf-8")
    n = swarm_doctor.write_missing_hashes(swarm_path, tmp_path)
    assert n == 0


def test_under_root_distinguishes_oserror_from_a_real_escape(tmp_path, monkeypatch):
    # a permission error or symlink loop hit while resolving is a could-not-check condition,
    # not a security-relevant "this tries to escape --root" claim, and the two must never
    # collapse into the same wording.
    real_resolve = pathlib.Path.resolve

    def _boom(self, *a, **kw):
        if self.name == "explodes.md":
            raise OSError("simulated permission error")
        return real_resolve(self, *a, **kw)

    monkeypatch.setattr(pathlib.Path, "resolve", _boom)
    status, detail = swarm_doctor._under_root(tmp_path, "explodes.md")
    assert status == "error"
    assert "simulated permission error" in detail


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


def test_r06_finding_when_declared_script_escapes_root_absolute(tmp_path):
    outside = tmp_path.parent / "not_under_root.py"
    outside.write_text("", encoding="utf-8")
    swarm = {"agents": {"a": _agent(scripts=[{"name": str(outside), "purpose": "p", "when": "w"}])}}
    results = swarm_doctor.rule_scripts_declared(swarm, tmp_path)
    assert len(results) == 1
    assert "escapes --root" in results[0].detail


def test_r06_finding_when_declared_script_escapes_root_dotdot(tmp_path):
    swarm = {"agents": {"a": _agent(scripts=[{"name": "../outside.py", "purpose": "p", "when": "w"}])}}
    results = swarm_doctor.rule_scripts_declared(swarm, tmp_path)
    assert len(results) == 1
    assert "escapes --root" in results[0].detail


@pytest.mark.skipif(
    sys.platform.startswith("win"),
    reason="a literal backslash is a reserved Windows filename character (illegal in any "
           "NTFS/FAT filename, not merely path-separator-ambiguous), so this scenario cannot "
           "be constructed on Windows at all -- untestable there rather than differently "
           "testable (#25).",
)
def test_r06_declared_name_with_backslash_is_one_literal_filename(tmp_path):
    # deliberately NOT treated as a path separator: a real POSIX filename may legitimately
    # contain a literal backslash, and normalizing it to a separator would mangle an exact,
    # correct declaration into a different path that does not exist (a real regression found
    # in review). A Windows-style declaration using backslash as a separator is expected to be
    # reported as a finding on POSIX, not silently guessed at.
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "known\\backslash.py").write_text("", encoding="utf-8")
    swarm = {"agents": {"a": _agent(scripts=[{"name": "scripts/known\\backslash.py", "purpose": "p", "when": "w"}])}}
    results = swarm_doctor.rule_scripts_declared(swarm, tmp_path)
    assert results == [swarm_doctor.Result(
        "R06 every declared script exists; every file under scripts/ is declared by some agent", "ok", "warning")]


def test_r06_case_mismatch_between_declared_and_disk_is_a_known_platform_gap(tmp_path):
    # Documents current, deliberately unfixed behavior rather than asserting a specific outcome:
    # a declared name that differs only in case from the file on disk depends on the OS's own
    # filesystem case-sensitivity for the "exists under --root" half of this check (is_file()),
    # while the orphan-direction comparison is always exact-match -- so the same swarm.json can
    # report differently on a case-sensitive filesystem (Linux) than on a case-insensitive one
    # (macOS, Windows). See trap.d/4.r06-case-sensitivity-platform-gap.md.
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "known.py").write_text("", encoding="utf-8")
    swarm = {"agents": {"a": _agent(scripts=[{"name": "scripts/Known.py", "purpose": "p", "when": "w"}])}}
    results = swarm_doctor.rule_scripts_declared(swarm, tmp_path)
    # the orphan side is always exact-match: "known.py" on disk is reported as undeclared
    # regardless of platform, since the declared name "Known.py" never appears verbatim
    assert any("not declared by any agent" in r.detail and "known.py" in r.detail for r in results)


def test_plain_text_output_sanitizes_embedded_newlines(tmp_path):
    # a swarm.json value is untrusted on an external pull request; an embedded newline in a
    # finding's detail must not be able to forge a second, fake result line in plain-text mode.
    forged_line = "ok               error    R05 FORGED"
    injected_md = "agents/x.md\n" + forged_line
    swarm = {"name": "s", "version": 1, "agents": {"a": _agent(md=injected_md)}, "flows": {}}
    swarm_path = tmp_path / "swarm.json"
    swarm_path.write_text(json.dumps(swarm), encoding="utf-8")
    out = subprocess.run([sys.executable, str(ROOT / "scripts" / "swarm_doctor.py"), str(swarm_path), "--root", str(tmp_path)],
                         capture_output=True, text=True)
    assert forged_line not in out.stdout.splitlines()
