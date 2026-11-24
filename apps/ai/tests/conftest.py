"""Shared test setup."""

import pytest


@pytest.fixture(autouse=True)
def _waiting_mode_from_the_test(monkeypatch):
    """The repo-root .env may set TEAM_FILLERS (1 to 4) for the team's live tests. Every test starts with it OFF and sets
    the mode it exercises itself, so the suite gives the same result on every laptop."""
    monkeypatch.delenv("TEAM_FILLERS", raising=False)
    monkeypatch.delenv("TEAM_ROUTER", raising=False)
    monkeypatch.delenv("TEAM_SLIM_PROMPT", raising=False)
    monkeypatch.delenv("TEAM_ORCHESTRATOR", raising=False)
