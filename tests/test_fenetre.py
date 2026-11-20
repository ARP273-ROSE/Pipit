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
    z.actualiser(attendre=True)            # la liste se lit en arrière-plan : on attend la première
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
    zone.construire_menu(zone.menu, complet=False)
    textes = _textes(zone.menu)
    assert textes[0] == tr("zone.titre")
    assert any(t.startswith("E:  SanDisk") for t in textes)
    assert tr("zone.tout") in textes and tr("zone.plus") in textes
    assert tr("menu.quitter") not in textes                    # clic gauche : éjecter seulement
    zone.construire_menu(zone.menu_complet, complet=True)
    complet = _textes(zone.menu_complet)
    assert tr("menu.quitter") in complet and tr("zone.forcer") in complet and tr("zone.coupables") in complet
    assert "Pipit — 7" in zone.tray.toolTip()


def test_icone_avec_compteur(zone):
    assert not zone.tray.icon().isNull()
    zone.reglages.compteur = False
    zone.actualiser()
    assert not zone.tray.icon().isNull()


def test_remontage_dans_le_menu(app, zone):
    p = [p for p in zone.lister() if "VID_0951" in p.id][0]
    zone.ejecter(p)
    assert attendre(app, lambda: not zone.en_cours)
    zone.actualiser(attendre=True)
    zone.construire_menu(zone.menu, complet=False)
    textes = _textes(zone.menu)
    assert tr("zone.remonter_titre") in textes
    action = [a for a in zone.menu.actions() if a.text().startswith(tr("zone.remonter", nom="")[:6])][-1]
    action.trigger()
    assert attendre(app, lambda: not zone.en_cours)
    assert any("VID_0951" in q.id for q in zone.lister())


def test_theme_change(app, zone):
    zone.ouvrir_reglages()
    f = zone.fenetre
    fond_sombre = app.palette().window().color().lightness()
    f.cb_theme.setCurrentIndex(f.cb_theme.findData("clair"))
    assert reglages.charger().theme == "clair"
    assert app.palette().window().color().lightness() > fond_sombre
    f.cb_theme.setCurrentIndex(f.cb_theme.findData("sombre"))


def test_type_et_icone_personnalises(app, zone, tmp_path):
    from PyQt6 import QtGui
    from pipit.fenetre import COL_TYPE
    zone.ouvrir_reglages()
    f = zone.fenetre
    cb = f.table.cellWidget(0, COL_TYPE)
    cb.setCurrentIndex(cb.findData("hdd"))
    mat = f.table.item(0, 2).data(QtCore.Qt.ItemDataRole.UserRole)
    assert reglages.charger().types[mat] == "hdd"
    image = tmp_path / "rouge.png"
    pm = QtGui.QPixmap(40, 40)
    pm.fill(QtGui.QColor("red"))
    pm.save(str(image))
    f.choisir_icone(mat, str(image))
    assert reglages.charger().icones[mat].endswith(".png")


def test_nom_choisi_dans_le_menu(zone):
    zone.reglages.noms["USB\\VID_0781&PID_558C"] = "Sauvegarde photo"
    zone.actualiser(attendre=True)
    zone.construire_menu(zone.menu, complet=False)
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
    assert f.table.rowCount() == 7
    f.table.item(0, COL_NOM).setText("Ma sauvegarde")
    f.table.item(0, COL_MASQUE).setCheckState(QtCore.Qt.CheckState.Checked)
    r = reglages.charger()
    assert r.noms == {"USB\\VID_0781&PID_558C": "Ma sauvegarde"}
    assert r.masques == ["USB\\VID_0781&PID_558C"]
    zone.actualiser(attendre=True)
    zone.construire_menu(zone.menu, complet=False)
    assert not any("Ma sauvegarde" in t for t in _textes(zone.menu))
    f.close()
    assert not f.isVisible()            # cachée, pas détruite : Pipit continue


def test_raccourci_change(zone):
    zone.ouvrir_reglages()
    f = zone.fenetre
    f.cb_menu.setCurrentIndex(f.cb_menu.findData("Ctrl+Alt+E"))
    assert reglages.charger().raccourci_menu == "Ctrl+Alt+E"


def test_fenetre_en_anglais(app, zone):
    zone.ouvrir_reglages()
    f = zone.fenetre
    if f.cb_langue.currentData() == "en":           # langue mémorisée par un essai précédent
        f.cb_langue.setCurrentIndex(f.cb_langue.findData("fr"))
        assert attendre(app, lambda: "réglages" in f.windowTitle())
        f = zone.fenetre
    f.cb_langue.setCurrentIndex(f.cb_langue.findData("en"))
    assert attendre(app, lambda: "settings" in f.windowTitle())
    for _ in range(5):
        app.processEvents()           # l'ancien contenu est détruit ici, sans planter
    assert f.windowTitle().startswith("Pipit") and "settings" in f.windowTitle()
    zone.construire_menu(zone.menu, complet=False)
    assert _textes(zone.menu)[0] == "Safely remove:"
    f.cb_langue.setCurrentIndex(f.cb_langue.findData("fr"))
    assert attendre(app, lambda: "réglages" in f.windowTitle())


def test_raison_du_refus(zone):
    from pipit import peripheriques
    r = peripheriques.Resultat(False, peripheriques.VETO_SERVICE, "SysMain")
    assert "SysMain" in zone.raison(r)


def test_tout_ejecter_ne_touche_ni_tiroir_ni_iso(app, zone):
    from pipit import demo
    zone.tout_ejecter()
    assert attendre(app, lambda: not zone.en_cours)
    restants = {p.type for p in zone.lister()}
    assert restants == {"optique", "virtuel"} and not demo._tiroirs


def test_reglages_par_appareil(app, zone, tmp_path, monkeypatch):
    from PyQt6 import QtWidgets
    from pipit import demo
    boites = []                     # sous Windows sans écran, RegisterHotKey échoue : boîte « pris »
    monkeypatch.setattr(QtWidgets.QMessageBox, "warning", lambda *a, **k: boites.append(a))
    from pipit.fenetre import COL_OPTIONS, COL_VITESSE, DialogueAppareil
    zone.ouvrir_reglages()
    f = zone.fenetre
    ligne = [i for i in range(f.table.rowCount()) if "VID_0951" in f.table.item(i, 0).toolTip()][0]
    assert "USB 2.0" in f.table.item(ligne, COL_VITESSE).text() and "⚠" in f.table.item(ligne, COL_VITESSE).text()
    assert f.table.cellWidget(ligne, COL_OPTIONS) is not None
    p = [p for p in zone._tous if "VID_0951" in p.id][0]
    programme = tmp_path / "outil.exe"
    programme.write_text("")
    dlg = DialogueAppareil(f, p)
    dlg.cb_lettre.setCurrentIndex(dlg.cb_lettre.findData("K"))
    dlg.e_programme.setText(str(programme))
    dlg.cb_raccourci.setCurrentIndex(dlg.cb_raccourci.findData("Ctrl+Alt+3"))
    dlg.c_courant.setChecked(True)
    dlg.appliquer()
    assert attendre(app, lambda: not zone.en_cours)
    r = reglages.charger()
    assert r.lettres_fixes[p.materiel] == "K" and r.au_branchement[p.materiel] == str(programme)
    assert r.raccourcis_appareils[p.materiel] == "Ctrl+Alt+3"
    assert r.courant_coupe == [p.materiel] and demo._courant[p.id] is True
    zone.actualiser(attendre=True)
    assert attendre(app, lambda: any(q.lettres == ["K"] for q in zone._tous if "VID_0951" in q.id))
    demo.remettre()


def test_arrivee_lettre_differente_propose_de_la_remettre(app, zone):
    from pipit import demo
    p = [p for p in zone.lister() if "VID_0951" in p.id][0]
    zone.reglages.lettres_fixes[p.materiel] = "K"
    zone._ids_connus = {q.id for q in zone._tous if q.id != p.id}     # comme s'il venait d'arriver
    zone._liste_recue(zone.lister(avec_masques=True), [])
    assert zone._action_message is not None
    zone._message_clique()
    assert attendre(app, lambda: not zone.en_cours)
    assert [q.lettres for q in zone.lister() if "VID_0951" in q.id] == [["K"]]
    demo.remettre()


def test_raccourci_par_appareil(app, zone):
    zone.reglages.raccourcis_appareils["USB\\VID_0951&PID_1666"] = "Ctrl+Alt+7"
    zone.appliquer_raccourcis()
    zone.actualiser(attendre=True)
    zone.ejecter_materiel("USB\\VID_0951&PID_1666")
    assert attendre(app, lambda: not zone.en_cours)
    assert not any("VID_0951" in q.id for q in zone.lister())
