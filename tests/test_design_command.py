import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_design_command_exists_and_has_frontmatter():
    p = ROOT / "commands" / "design.md"
    assert p.exists()
    src = p.read_text(encoding="utf-8")
    assert src.startswith("---\n")
    assert "description:" in src


def test_design_command_is_prose_no_script():
    src = (ROOT / "commands" / "design.md").read_text(encoding="utf-8")
    assert "```bash" not in src


def test_design_command_covers_interview_and_restatement():
    src = (ROOT / "commands" / "design.md").read_text(encoding="utf-8")
    assert "one question at a time" in src.lower()
    assert "irreversible" in src
    assert "restat" in src.lower()


def test_design_command_refuses_presets_and_guessed_cost():
    src = (ROOT / "commands" / "design.md").read_text(encoding="utf-8")
    assert "examples/claude-oss.swarm.json" in src
    assert "template" in src.lower()
    assert "cost_tokens" in src
    assert "never guess" in src.lower() or "leave it absent" in src.lower()


def test_design_command_wires_picture_and_handoff():
    src = (ROOT / "commands" / "design.md").read_text(encoding="utf-8")
    assert "/swarm-builder:read" in src
    assert "/swarm-builder:compile" in src


def test_design_command_referenced_and_unmarked_in_readme():
    src = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "/swarm-builder:design" in src
    assert "(planned, #30)" not in src
