"""Réglages communs : périphériques imités, données dans un dossier jetable."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("PIPIT_DEMO", "1")            # tests/test_windows.py le remet à 0

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def donnees(tmp_path, monkeypatch):
    monkeypatch.setenv("PIPIT_DONNEES", str(tmp_path / "donnees"))
    if os.environ.get("PIPIT_DEMO") == "1":
        from pipit import demo
        demo.remettre()
    return tmp_path / "donnees"
