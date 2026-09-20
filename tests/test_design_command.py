import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_design_command_exists_and_has_frontmatter():
    p = ROOT / "commands" / "design.md"
    assert p.exists()
    src = p.read_text(encoding="utf-8")
    assert src.startswith("---\n")
    assert "description:" in src


def test_design_command_is_prose_no_script():
    # Catches any fenced code block regardless of language tag (bash, sh, zsh, python, or
    # none at all) -- a narrower check that only matched the literal "```bash" spelling would
    # stay green if a script snippet were added under a different fence, which is exactly the
    # gap a reviewer would exploit to slip a script past this guard.
    src = (ROOT / "commands" / "design.md").read_text(encoding="utf-8")
    assert not re.search(r"^```", src, re.MULTILINE)


def test_design_command_covers_interview_and_restatement():
    src = (ROOT / "commands" / "design.md").read_text(encoding="utf-8")
    assert "one question at a time" in src.lower()
    assert "irreversible" in src
    assert "restat" in src.lower()


def test_design_command_refuses_presets_and_guessed_cost():
    # Substring presence alone is gameable -- prose that *told* the agent to start from the
    # example as a template, or to estimate cost_tokens, would still contain every one of
    # these words. Pin the actual prohibition each phrase sits inside, not just its vocabulary.
    src = (ROOT / "commands" / "design.md").read_text(encoding="utf-8")
    assert re.search(
        r"never start from `examples/claude-oss\.swarm\.json`[^.]*never copied as a template",
        src,
        re.IGNORECASE,
    )
    assert re.search(r"`cost_tokens`[^.]*measured[^.]*never guessed", src, re.IGNORECASE)
    assert "leave it absent and say so" in src


def test_design_command_wires_picture_and_handoff():
    src = (ROOT / "commands" / "design.md").read_text(encoding="utf-8")
    assert "/swarm-builder:read" in src
    assert "/swarm-builder:compile" in src


def test_design_command_referenced_and_unmarked_in_readme():
    src = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "/swarm-builder:design" in src
    assert "(planned, #30)" not in src
