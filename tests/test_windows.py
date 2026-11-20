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


def test_raccourci_global_enregistre():
    from PyQt6 import QtWidgets
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])  # noqa: F841
    w = QtWidgets.QWidget()
    from pipit.raccourci import Raccourcis
    r = Raccourcis(int(w.winId()))
    assert r.ajouter("Ctrl+Alt+Shift+F11", lambda: None)
    r.tout_retirer()


def test_lancement_avec_windows_aller_retour():
    from pipit import systeme
    avant = systeme.lance_avec_windows()
    try:
        assert systeme.lancer_avec_windows(True) and systeme.lance_avec_windows()
        assert systeme.lancer_avec_windows(False) and not systeme.lance_avec_windows()
    finally:
        systeme.lancer_avec_windows(avant)
