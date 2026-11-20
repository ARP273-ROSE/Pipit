"""Garde-fous de traduction."""
import re
import string
import subprocess
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
from pipit import i18n  # noqa: E402


def champs(modele: str) -> set:
    return {nom for _, nom, _, _ in string.Formatter().parse(modele) if nom}


def test_toutes_les_cles_dans_les_deux_langues():
    for cle, textes in i18n.TEXTES.items():
        for lg in i18n.LANGUES:
            assert textes.get(lg, "").strip(), f"{cle} : texte {lg} vide ou absent"


def test_memes_champs_de_format():
    for cle, textes in i18n.TEXTES.items():
        assert champs(textes["fr"]) == champs(textes["en"]), cle


def test_chaque_cle_utilisee_existe():
    """Une clé appelée par tr("…") sans texte afficherait la clé elle-même."""
    manquantes = []
    for f in [RACINE / "run.py", *sorted((RACINE / "pipit").glob("*.py"))]:
        for cle in re.findall(r'tr\("([a-z_.0-9]+)"[,)]', f.read_text(encoding="utf-8")):
            if cle not in i18n.TEXTES:
                manquantes.append(f"{f.name}: {cle}")
    assert not manquantes, manquantes


def test_cles_construites_existent():
    attendues = [f"menu.langue.{c}" for c in ("auto", "fr", "en")]
    assert [c for c in attendues if c not in i18n.TEXTES] == []


def test_aucun_francais_dans_l_anglais():
    accents = re.compile(r"[éèêàùçôî]")
    fautes = [c for c, t in i18n.TEXTES.items() if accents.search(t["en"]) and c != "menu.langue.fr"]
    assert not fautes, fautes


def test_cle_inconnue_ne_casse_rien():
    assert i18n.tr("cle.qui.n.existe.pas") == "cle.qui.n.existe.pas"


def test_detection_par_environnement(monkeypatch):
    for var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("LANG", "fr_FR.UTF-8")
    assert i18n.detecter() == "fr"
    monkeypatch.setenv("LANG", "de_DE.UTF-8")
    assert i18n.detecter() == "en"


def test_option_version():
    sortie = subprocess.run([sys.executable, str(RACINE / "run.py"), "--version"],
                            capture_output=True, text=True, timeout=60)
    assert sortie.returncode == 0 and sortie.stdout.startswith("Pipit ")
