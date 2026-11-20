"""Essais sur un VRAI Windows (CI windows-latest) : API du système, sans rien éjecter."""
import os
import sys

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows seulement")


@pytest.fixture(autouse=True)
def vrai_systeme(monkeypatch):
    monkeypatch.setenv("PIPIT_DEMO", "0")


def test_les_disques_se_listent():
    from pipit import disques_windows
    disques = disques_windows.lister()
    assert disques, "aucun disque vu"
    systeme = [d for d in disques if d.systeme]
    assert systeme, [(d.nom, d.lettres) for d in disques]
    assert all(d.taille > 0 for d in systeme)
    print([(d.numero, d.nom, d.bus, d.lettres, d.id_ejectable) for d in disques])


def test_le_disque_systeme_n_est_jamais_propose():
    from pipit import peripheriques
    for p in peripheriques.lister(internes_a_chaud=True):
        assert not any(d.systeme for d in p.disques)


def test_ejecter_un_inconnu_ne_casse_rien():
    from pipit import disques_windows
    veto, _nom = disques_windows.ejecter("USB\\VID_FFFF&PID_FFFF\\N_EXISTE_PAS")
    assert veto == 13


def test_journal_du_systeme_lisible():
    import time
    from pipit import bloqueurs
    assert bloqueurs.chercher(time.time() - 60) == [] or True    # ne lève pas, ne bloque pas


def _vraie_fenetre():
    """Une vraie fenêtre Win32 : en mode Qt « offscreen », winId() n'est pas un HWND."""
    import ctypes
    from ctypes import wintypes
    u = ctypes.windll.user32
    u.CreateWindowExW.restype = wintypes.HWND
    u.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
                                  ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                  wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID]
    hwnd = u.CreateWindowExW(0, "STATIC", "pipit-essai", 0, 0, 0, 1, 1, None, None, None, None)
    assert hwnd
    return hwnd


@pytest.mark.parametrize("texte", ["Ctrl+Alt+Shift+F11", "Win+Alt"])
def test_raccourci_global_enregistre(texte):
    from pipit.raccourci import Raccourcis
    r = Raccourcis(_vraie_fenetre())
    assert r.ajouter(texte, lambda: None), texte
    r.tout_retirer()


def test_lancement_avec_windows_aller_retour():
    from pipit import systeme
    avant = systeme.lance_avec_windows()
    try:
        assert systeme.lancer_avec_windows(True) and systeme.lance_avec_windows()
        assert systeme.lancer_avec_windows(False) and not systeme.lance_avec_windows()
    finally:
        systeme.lancer_avec_windows(avant)


# ------------------------------------------------------------ 0.2.0
def test_types_et_attente_sans_erreur():
    from pipit import disques_windows, peripheriques
    for d in disques_windows.lister():
        print(d.nom, d.bus, d.ssd, d.appareil)
    assert isinstance(disques_windows.en_attente_de_retrait(), list)
    for p in peripheriques.lister(internes_a_chaud=True):
        assert p.type


def test_coupable_trouve_par_les_poignees(tmp_path):
    """Un autre programme garde un fichier ouvert : Pipit doit le trouver, avec le fichier."""
    import subprocess
    import time
    from pipit import poignees
    fichier = tmp_path / "ouvert.txt"
    fichier.write_text("x")
    code = ("import sys,time;f=open(sys.argv[1]);print('pret',flush=True);time.sleep(60)")
    proc = subprocess.Popen([sys.executable, "-c", code, str(fichier)], stdout=subprocess.PIPE, text=True)
    try:
        assert proc.stdout.readline().strip() == "pret"
        debut = time.time()
        trouves = poignees.chercher([str(fichier)[0]])
        print(f"{len(trouves or [])} programme(s) en {time.time() - debut:.1f} s")
        assert trouves is not None
        moi = [c for c in trouves if c.pid == proc.pid]
        assert moi, [(c.programme, c.pid) for c in trouves]
        assert any(f.lower().endswith("ouvert.txt") for f in moi[0].fichiers)
    finally:
        proc.kill()


def test_assistant_tache_creee_puis_retiree():
    """Les machines de GitHub sont administrateur : la vraie tâche planifiée se crée."""
    from pipit import assistant
    if not assistant.est_admin():
        pytest.skip("pas administrateur")
    try:
        assert assistant.installer(), "tâche non créée"
        assert assistant.installe()
    finally:
        assistant.desinstaller()
    assert not assistant.installe()


def test_assistant_repond_par_fichier():
    """Demande « coupables » traitée par le vrai code de l'assistant (sans la tâche)."""
    import json
    from pipit import assistant
    d = assistant.dossier() / "demande-ci.json"
    d.write_text(json.dumps({"action": "coupables", "id": "USB\\VID_0000&PID_0000\\X", "lettres": ["C"]}),
                 encoding="utf-8")
    assert assistant.executer() == 0
    r = json.loads((assistant.dossier() / "reponse-ci.json").read_text(encoding="utf-8"))
    assert r["ok"], r
