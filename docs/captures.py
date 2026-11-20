"""Fabrique les captures du manuel, sans écran :

    QT_QPA_PLATFORM=offscreen python docs/captures.py

Mode démonstration : périphériques fictifs (noms de matériel génériques),
aucun nom ni chemin réel. Les données vont dans un dossier temporaire.
"""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["PIPIT_DEMO"] = "1"
os.environ["PIPIT_DONNEES"] = tempfile.mkdtemp(prefix="pipit-captures-")
ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI.parent))

from PyQt6 import QtCore, QtWidgets  # noqa: E402

from pipit import peripheriques, style  # noqa: E402
from pipit.i18n import definir_langue  # noqa: E402


def capturer_boite(boite, nom):
    boite.show()
    QtWidgets.QApplication.processEvents()
    boite.grab().save(str(ICI / nom))
    boite.done(0)


def main():
    app = QtWidgets.QApplication([])
    style.appliquer(app)
    from pipit.zone import Zone
    zone = Zone(app)
    zone.reglages.noms["USB\\VID_0781&PID_558C"] = "Sauvegarde photo"
    for lg in ("fr", "en"):
        definir_langue(lg)
        if lg == "en":
            zone.reglages.noms["USB\\VID_0781&PID_558C"] = "Photo backup"
        # menu de l'icône
        for menu, complet, nom in ((zone.menu, False, "menu"), (zone.menu_complet, True, "menu_complet")):
            zone.construire_menu(menu, complet=complet)
            menu.popup(QtCore.QPoint(10, 10))
            app.processEvents()
            menu.grab().save(str(ICI / f"capture_{nom}-{lg}.png"))
            menu.hide()
        # réglages
        zone.ouvrir_reglages()
        f = zone.fenetre
        f.cb_langue.blockSignals(True)
        f.cb_langue.setCurrentIndex(f.cb_langue.findData(lg))
        f.cb_langue.blockSignals(False)
        f._construire()
        f.rafraichir()
        f.resize(1000, 720)
        app.processEvents()
        f.grab().save(str(ICI / f"capture_reglages-{lg}.png"))
        f.hide()
        # refus, avec le programme en cause
        p = zone.lister()[0]
        from pipit import bloqueurs
        r = peripheriques.Resultat(False, peripheriques.VETO_FICHIER_OUVERT, "", bloqueurs.chercher(0))
        boites = []
        ancien = QtWidgets.QMessageBox.exec
        QtWidgets.QMessageBox.exec = lambda self: boites.append(self) or 0
        try:
            zone._refus(p, r)
            lecteur = [q for q in zone.lister() if q.lecteur_de_cartes][0]
            zone._confirmer_lecteur(lecteur)
        finally:
            QtWidgets.QMessageBox.exec = ancien
        capturer_boite(boites[0], f"capture_refus-{lg}.png")
        capturer_boite(boites[1], f"capture_lecteur-{lg}.png")
    print("captures :", sorted(p.name for p in ICI.glob("capture_*.png")))


if __name__ == "__main__":
    main()
