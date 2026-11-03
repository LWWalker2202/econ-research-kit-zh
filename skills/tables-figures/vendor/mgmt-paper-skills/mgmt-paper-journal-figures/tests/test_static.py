from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_skill_and_template_exist():
    assert (ROOT / "SKILL.md").is_file()
    assert (ROOT / "templates/python/journal_figure.py").is_file()


def test_nature_checklist_mentions_core_gates():
    text = (ROOT / "references/nature-level-checklist.md").read_text(encoding="utf-8")
    for token in ["grayscale", "Fonts", "script"]:
        assert token.lower() in text.lower()


def test_journal_profiles_cover_utd_management_core():
    text = (ROOT / "references/journal-profiles.md").read_text(encoding="utf-8")
    for token in [
        "Academy of Management Journal",
        "Administrative Science Quarterly",
        "Organization Science",
        "Strategic Management Journal",
        "Management Science",
        "UTD 24",
    ]:
        assert token in text


def test_template_has_fallback_and_management_profiles():
    text = (ROOT / "templates/python/journal_figure.py").read_text(encoding="utf-8")
    assert "fallback_svg" in text
    assert "Academy of Management Journal" in text
    assert "Administrative Science Quarterly" in text
