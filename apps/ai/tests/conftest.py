"""Shared test setup."""

import os

import pytest


@pytest.fixture(autouse=True)
def _team_switches_from_the_test(monkeypatch):
    """The repo-root .env (and docker compose) set the team's TEAM_* switches for live tests. Every test starts with
    ALL of them off, including switches added later, and sets the ones it exercises itself, so the suite gives the
    same result on every laptop and in the container. TEAM_FAST_MODEL is a model name, not a switch: kept."""
    for name in list(os.environ):
        if name.startswith("TEAM_") and name != "TEAM_FAST_MODEL":
            monkeypatch.delenv(name, raising=False)
