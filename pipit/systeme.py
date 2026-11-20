"""Dossier des données, lancement avec Windows, ouverture de l'Explorateur."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

NOM = "Pipit"
WINDOWS = sys.platform == "win32"
CLE_RUN = r"Software\Microsoft\Windows\CurrentVersion\Run"


def installe() -> bool:
    python = Path(__file__).resolve().parent.parent.parent / "python"
    return (python / "python.exe").exists() or (python / "bin" / "python3").exists()


def dossier_donnees() -> Path:
    """Données hors du dossier d'installation : elles survivent aux mises à jour."""
    if os.environ.get("PIPIT_DONNEES"):
        base = Path(os.environ["PIPIT_DONNEES"])
    elif not installe():
        base = Path(__file__).resolve().parent.parent / "_donnees"
    elif WINDOWS:
        base = Path(os.environ.get("LOCALAPPDATA", Path.home())) / NOM
    else:
        base = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state") / NOM
    try:
        base.mkdir(parents=True, exist_ok=True)
    except OSError:
        base = Path.home()
    return base


def executable_fenetre() -> str:
    """pythonw.exe à côté de python.exe : aucune console qui s'ouvre."""
    exe = Path(sys.executable)
    if WINDOWS:
        w = exe.with_name("pythonw.exe")
        if w.exists():
            return str(w)
    return str(exe)


def commande_demarrage() -> str:
    script = Path(__file__).resolve().parent.parent / "run.py"
    return subprocess.list2cmdline([executable_fenetre(), str(script), "--discret"])


def lance_avec_windows() -> bool:
    if not WINDOWS:
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, CLE_RUN) as k:
            winreg.QueryValueEx(k, NOM)
            return True
    except OSError:
        return False


def lancer_avec_windows(oui: bool) -> bool:
    """Valeur « Pipit » de HKCU\\…\\Run : par utilisateur, aucune élévation."""
    if not WINDOWS:
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, CLE_RUN, 0, winreg.KEY_SET_VALUE) as k:
            if oui:
                winreg.SetValueEx(k, NOM, 0, winreg.REG_SZ, commande_demarrage())
            else:
                try:
                    winreg.DeleteValue(k, NOM)
                except FileNotFoundError:
                    pass
        return True
    except OSError:
        return False


def ouvrir_lecteur(lettre: str) -> None:
    if WINDOWS:
        os.startfile(f"{lettre}:\\")          # noqa: S606 — l'Explorateur, rien d'autre
