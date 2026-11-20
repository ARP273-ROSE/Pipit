"""Interface (Qt hors écran) : menu de l'icône, éjection, réglages."""
import pytest
from PyQt6 import QtCore, QtWidgets

from pipit import reglages
from pipit.i18n import definir_langue, tr


@pytest.fixture(scope="module")
def app():
    a = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    from pipit import style
    style.appliquer(a)
    return a


@pytest.fixture
def zone(app):
    definir_langue("fr")
    from pipit.zone import Zone
    z = Zone(app)
    yield z
    z.minuteur.stop()
    z.raccourcis.tout_retirer()
    z.tray.hide()


def _textes(menu):
    return [a.text() for a in menu.actions() if not a.isSeparator()]


def attendre(app, condition, delai=5.0):
    minuterie = QtCore.QElapsedTimer()
    minuterie.start()
    while not condition() and minuterie.elapsed() < delai * 1000:
        app.processEvents()
    return condition()


def test_menu_liste_les_peripheriques(zone):
    zone.construire_menu()
    textes = _textes(zone.menu)
    assert textes[0] == tr("zone.titre")
    assert any(t.startswith("E:  SanDisk") for t in textes)
    assert tr("zone.tout") in textes and tr("menu.quitter") in textes
    assert "Pipit — 3" in zone.tray.toolTip()


def test_nom_choisi_dans_le_menu(zone):
    zone.reglages.noms["USB\\VID_0781&PID_558C"] = "Sauvegarde photo"
    zone.construire_menu()
    assert any("Sauvegarde photo" in t for t in _textes(zone.menu))


def test_ejection_par_le_menu(app, zone):
    p = [p for p in zone.lister() if "VID_0951" in p.id][0]
    zone.ejecter(p)
    assert attendre(app, lambda: not zone.en_cours)
    assert not any("VID_0951" in q.id for q in zone.lister())


def test_reglages_nom_et_masque(app, zone):
    from pipit.fenetre import COL_MASQUE, COL_NOM
    zone.ouvrir_reglages()
    f = zone.fenetre
    assert f.table.rowCount() == 3
    f.table.item(0, COL_NOM).setText("Ma sauvegarde")
    f.table.item(0, COL_MASQUE).setCheckState(QtCore.Qt.CheckState.Checked)
    r = reglages.charger()
    assert r.noms == {"USB\\VID_0781&PID_558C": "Ma sauvegarde"}
    assert r.masques == ["USB\\VID_0781&PID_558C"]
    zone.construire_menu()
    assert not any("Ma sauvegarde" in t for t in _textes(zone.menu))
    f.close()
    assert not f.isVisible()            # cachée, pas détruite : Pipit continue


def test_raccourci_change(zone):
    zone.ouvrir_reglages()
    f = zone.fenetre
    f.cb_menu.setCurrentIndex(f.cb_menu.findData("Ctrl+Alt+E"))
    assert reglages.charger().raccourci_menu == "Ctrl+Alt+E"


def test_fenetre_en_anglais(zone):
    zone.ouvrir_reglages()
    f = zone.fenetre
    f.cb_langue.setCurrentIndex(f.cb_langue.findData("en"))
    assert f.windowTitle().startswith("Pipit") and "settings" in f.windowTitle()
    zone.construire_menu()
    assert _textes(zone.menu)[0] == "Safely remove:"
    f.cb_langue.setCurrentIndex(f.cb_langue.findData("fr"))


def test_raison_du_refus(zone):
    from pipit import peripheriques
    r = peripheriques.Resultat(False, peripheriques.VETO_SERVICE, "SysMain")
    assert "SysMain" in zone.raison(r)
