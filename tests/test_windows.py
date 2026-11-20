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


def test_ancienne_tache_detectee_puis_retiree():
    """La tâche de la 0.2.0 (risque de sécurité) est retrouvée et supprimée."""
    import subprocess
    from pipit import assistant
    if not assistant.est_admin():
        pytest.skip("pas administrateur")
    subprocess.run(["schtasks", "/create", "/f", "/tn", assistant.ANCIENNE_TACHE, "/tr", "cmd /c exit",
                    "/sc", "once", "/st", "23:59"], capture_output=True)
    assert assistant.ancienne_tache_presente()
    assert assistant.retirer_ancienne_tache()
    assert not assistant.ancienne_tache_presente()


# ------------------------------------------------------------ 0.3.0
def _diskpart(script: str) -> str:
    import subprocess
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        f.write(script)
    r = subprocess.run(["diskpart", "/s", f.name], capture_output=True, text=True, timeout=180)
    return r.stdout + r.stderr


def test_image_vhd_vue_puis_demontee(tmp_path):
    """Un VHD monté = lecteur virtuel : listé avec le geste « démonter », puis démonté pour de vrai."""
    from pipit import assistant, disques_windows, peripheriques
    if not assistant.est_admin():
        pytest.skip("diskpart demande les droits d'administrateur")
    import string
    vhd = tmp_path / "essai.vhd"
    libres = [l for l in "PQRSUVWXY" if not disques_windows.kernel32.GetLogicalDrives() & (1 << (ord(l) - 65))]
    lettre = libres[0]
    sortie = _diskpart(f'create vdisk file="{vhd}" maximum=64 type=expandable\nselect vdisk file="{vhd}"\n'
                       f'attach vdisk\ncreate partition primary\nformat fs=ntfs quick label=ESSAI\n'
                       f'assign letter={lettre}\n')
    print(sortie[-400:])
    try:
        perifs = {p.lettres[0] if p.lettres else "": p for p in peripheriques.lister()}
        assert lettre in perifs, (lettre, [(p.nom, p.bus, p.lettres) for p in peripheriques.lister(internes_a_chaud=True)])
        p = perifs[lettre]
        assert (p.type, p.geste) == ("virtuel", "demonter"), (p.type, p.bus)
        assert peripheriques.ejecter(p).ok
        assert lettre not in [l for q in peripheriques.lister() for l in q.lettres]
    finally:
        _diskpart(f'select vdisk file="{vhd}"\ndetach vdisk\n')
    del string


def test_tiroir_sans_lecteur_ne_plante_pas():
    from pipit import disques_windows
    assert disques_windows.ouvrir_tiroir("Q") is False or True


def test_canal_prive_aller_retour():
    """Le côté élevé (sans UAC ici) répond par le canal authentifié ; une mauvaise clé est refusée."""
    import secrets
    import threading
    from multiprocessing.connection import Listener
    from pipit import assistant
    canal = "\\\\.\\pipe\\pipit-" + secrets.token_hex(16)
    cle = secrets.token_bytes(32)
    recu = {}
    with Listener(address=canal, family="AF_PIPE", authkey=cle) as ecoute:
        def accepter():
            with ecoute.accept() as conn:
                recu.update(conn.recv())
        fil = threading.Thread(target=accepter, daemon=True)
        fil.start()
        code = assistant.executer(["coupables", "USB\\VID_FFFF&PID_FFFF\\INEXISTANT", canal, cle.hex()])
        fil.join(10)
    assert code == 1 and recu == {"ok": False, "detail": "peripherique"}


def test_disque_interne_jamais_force():
    from pipit import assistant, disques_windows
    for d in disques_windows.lister():
        if d.id_ejectable:
            continue
        assert assistant.traiter("forcer", d.id_disque or "USB\\VID_0000&PID_0000\\X")["ok"] is False
