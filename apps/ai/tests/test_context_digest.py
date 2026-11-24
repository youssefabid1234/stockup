"""TEAM_SLIM_PROMPT: only the essential sections of the company context go into the prompt."""

from app.agent import context_digest as cd
from app.agent import prompts

DOC = """# The Furnil — Presentation

Toulouse distributor.

## Key figures

- 104 customers

## House rules

- Free delivery from 150 € HT.

## Current situation on 24/11 (to be known)

- AOP laminating butter is out of stock.
"""


def test_digest_keeps_only_the_listed_sections():
    out = cd.digest(DOC, ("House rules", "Current situation on"))
    assert "Toulouse distributor" in out and "Free delivery from 150" in out and "AOP laminating butter is out of stock" in out
    assert "Key figures" not in out and "104 customers" not in out


def test_unknown_headings_keep_the_whole_file():
    assert cd.digest(DOC, ("None of this",)) == DOC.strip()


def test_slim_prompt_follows_its_switch(monkeypatch, tmp_path):
    folder = tmp_path / "context"
    folder.mkdir()
    (folder / "01-entreprise.md").write_text(DOC, encoding="utf-8")
    (folder / "99-autre.md").write_text("# Other\n\nEverything's kept.", encoding="utf-8")
    from types import SimpleNamespace

    fake = SimpleNamespace(data_dir=tmp_path)  # settings is frozen: swap the whole object in both modules
    monkeypatch.setattr(prompts, "settings", fake)
    monkeypatch.setattr(cd, "settings", fake)
    monkeypatch.delenv("TEAM_SLIM_PROMPT", raising=False)
    assert "104 customers" in prompts.company_context()
    monkeypatch.setenv("TEAM_SLIM_PROMPT", "1")
    slim = prompts.company_context()
    assert "104 customers" not in slim and "Free delivery from 150" in slim and "Everything's kept." in slim


def test_real_pack_is_at_least_halved():
    full, slim = prompts.read_context_files(), cd.read_context_digest()
    if not full:  # no data pack mounted
        return
    assert len(slim) < len(full) / 2
    for must in ("House rules", "Current situation on", "Ambiguous Alias", "Limit times", "Credit and collections"):
        assert must in slim
