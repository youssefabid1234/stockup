"""TEAM_SLIM_PROMPT: only the essential sections of the company context go into the prompt."""

from app.agent import context_digest as cd
from app.agent import prompts

DOC = """# Le Fournil — présentation

Distributeur toulousain.

## Chiffres clés

- 104 clients

## Règles de la maison

- Franco 150 € HT.

## Situation au 24/11 (à connaître)

- Rupture tourage AOP.
"""


def test_digest_keeps_only_the_listed_sections():
    out = cd.digest(DOC, ("Règles de la maison", "Situation au"))
    assert "Distributeur toulousain" in out and "Franco 150" in out and "Rupture tourage" in out
    assert "Chiffres clés" not in out and "104 clients" not in out


def test_unknown_headings_keep_the_whole_file():
    assert cd.digest(DOC, ("Rien de tout ça",)) == DOC.strip()


def test_slim_prompt_follows_its_switch(monkeypatch, tmp_path):
    folder = tmp_path / "context"
    folder.mkdir()
    (folder / "01-entreprise.md").write_text(DOC, encoding="utf-8")
    (folder / "99-autre.md").write_text("# Autre\n\nTout est gardé.", encoding="utf-8")
    from types import SimpleNamespace

    fake = SimpleNamespace(data_dir=tmp_path)  # settings is frozen: swap the whole object in both modules
    monkeypatch.setattr(prompts, "settings", fake)
    monkeypatch.setattr(cd, "settings", fake)
    monkeypatch.delenv("TEAM_SLIM_PROMPT", raising=False)
    assert "104 clients" in prompts.company_context()
    monkeypatch.setenv("TEAM_SLIM_PROMPT", "1")
    slim = prompts.company_context()
    assert "104 clients" not in slim and "Franco 150" in slim and "Tout est gardé." in slim


def test_real_pack_is_at_least_halved():
    full, slim = prompts.read_context_files(), cd.read_context_digest()
    if not full:  # no data pack mounted
        return
    assert len(slim) < len(full) / 2
    for must in ("Règles de la maison", "Situation au", "Alias ambigus", "Heures limites", "Crédit et relances"):
        assert must in slim
