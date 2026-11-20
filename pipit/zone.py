"""L'icône près de l'horloge : le menu des périphériques, l'éjection, les raccourcis."""
from __future__ import annotations

import threading
from pathlib import Path

from PyQt6 import QtCore, QtGui, QtWidgets

from . import __version__, bloqueurs, peripheriques, reglages, systeme
from .i18n import langue, tr
from .modele import Peripherique, taille_lisible

RACINE = Path(__file__).resolve().parent.parent


class _FiltreNatif(QtCore.QAbstractNativeEventFilter):
    def __init__(self, raccourcis):
        super().__init__()
        self.raccourcis = raccourcis

    def nativeEventFilter(self, type_evt, message):
        if type_evt == b"windows_generic_MSG" and self.raccourcis is not None:
            from ctypes import wintypes
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == 0x0312 and self.raccourcis.message(msg.message, msg.wParam):
                return True, 0
        return False, 0


class Zone(QtCore.QObject):
    fini = QtCore.pyqtSignal(object, object)          # (périphérique, Resultat)

    def __init__(self, app: QtWidgets.QApplication):
        super().__init__()
        self.app = app
        self.reglages = reglages.charger()
        self.fenetre = None
        self.en_cours: set[str] = set()
        self._derniers: list[Peripherique] = []
        icone = RACINE / "logo_32.png"
        self.icone = QtGui.QIcon(str(icone)) if icone.exists() else app.style().standardIcon(
            QtWidgets.QStyle.StandardPixmap.SP_DriveHDIcon)
        self.tray = QtWidgets.QSystemTrayIcon(self.icone)
        self.menu = QtWidgets.QMenu()
        self.menu.aboutToShow.connect(self.construire_menu)
        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(self._clic)
        self.fini.connect(self._resultat)
        # fenêtre invisible : reçoit WM_HOTKEY et donne le premier plan au menu
        self.ancre = QtWidgets.QWidget()
        self.ancre.setWindowFlags(QtCore.Qt.WindowType.Tool | QtCore.Qt.WindowType.FramelessWindowHint)
        self.ancre.resize(1, 1)
        self.raccourcis = None
        self.filtre = None
        self.appliquer_raccourcis()
        self.minuteur = QtCore.QTimer(self)
        self.minuteur.timeout.connect(self.actualiser)
        self.minuteur.start(2500)
        self.actualiser()
        self.tray.show()

    # ------------------------------------------------------------ liste
    def lister(self, avec_masques: bool = False) -> list[Peripherique]:
        try:
            return peripheriques.lister(set(self.reglages.masques), self.reglages.internes_a_chaud,
                                        avec_masques=avec_masques)
        except Exception:                                # noqa: BLE001 — l'icône ne doit pas mourir
            return []

    def actualiser(self) -> None:
        self._derniers = self.lister()
        n = len(self._derniers)
        self.tray.setToolTip(tr("zone.infobulle.aucun") if n == 0 else
                             tr("zone.infobulle.un") if n == 1 else tr("zone.infobulle.plusieurs", n=n))

    def nom(self, p: Peripherique) -> str:
        return self.reglages.noms.get(p.materiel) or p.nom

    def libelle(self, p: Peripherique) -> str:
        lettres = ", ".join(f"{l}:" for l in p.lettres)
        morceaux = [lettres, self.nom(p)]
        taille = taille_lisible(p.taille, langue())
        if taille:
            morceaux.append(f"({taille})")
        elif not p.lettres:
            morceaux.append(tr("zone.vide"))
        return "  ".join(m for m in morceaux if m)

    # ------------------------------------------------------------ menu
    def construire_menu(self) -> None:
        self.menu.clear()
        self.actualiser()
        titre = self.menu.addAction(tr("zone.titre"))
        titre.setEnabled(False)
        if not self._derniers:
            self.menu.addAction(tr("zone.aucun")).setEnabled(False)
        icone_disque = self.app.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_DriveHDIcon)
        for p in self._derniers:
            a = self.menu.addAction(icone_disque, self.libelle(p))
            a.setToolTip(p.id)
            a.setEnabled(p.id not in self.en_cours)
            a.triggered.connect(lambda _=False, p=p: self.ejecter(p))
        if len(self._derniers) > 1:
            self.menu.addSeparator()
            self.menu.addAction(tr("zone.tout"), self.tout_ejecter)
        lettres = [(l, p) for p in self._derniers for l in p.lettres]
        if lettres:
            sous = self.menu.addMenu(tr("zone.ouvrir"))
            for l, p in lettres:
                sous.addAction(f"{l}:  {self.nom(p)}", lambda l=l: systeme.ouvrir_lecteur(l))
        self.menu.addSeparator()
        self.menu.addAction(tr("zone.reglages"), self.ouvrir_reglages)
        self.menu.addAction(tr("menu.manuel"), self.ouvrir_manuel)
        self.menu.addSeparator()
        self.menu.addAction(tr("menu.quitter"), self.quitter)

    def _clic(self, raison) -> None:
        if raison in (QtWidgets.QSystemTrayIcon.ActivationReason.Trigger,
                      QtWidgets.QSystemTrayIcon.ActivationReason.DoubleClick):
            self.montrer_menu()

    def montrer_menu(self) -> None:
        """Au curseur ; la fenêtre invisible prend le premier plan, sinon le menu
        ne se refermerait pas en cliquant ailleurs (règle connue de Windows)."""
        self.ancre.move(QtGui.QCursor.pos())
        self.ancre.show()
        self.ancre.activateWindow()
        self.ancre.raise_()
        self.menu.popup(QtGui.QCursor.pos())
        self.menu.activateWindow()
        QtCore.QTimer.singleShot(0, self.ancre.hide)

    # ------------------------------------------------------------ raccourcis
    def appliquer_raccourcis(self) -> list[str]:
        """Enregistre les raccourcis ; renvoie ceux qu'un autre programme occupe déjà."""
        from .raccourci import Raccourcis
        if self.raccourcis is not None:
            self.raccourcis.tout_retirer()
        refuses = []
        hwnd = int(self.ancre.winId())
        self.raccourcis = Raccourcis(hwnd)
        if self.filtre is None:
            self.filtre = _FiltreNatif(self.raccourcis)
            self.app.installNativeEventFilter(self.filtre)
        self.filtre.raccourcis = self.raccourcis
        for texte, action in ((self.reglages.raccourci_menu, self.montrer_menu),
                              (self.reglages.raccourci_tout, self.tout_ejecter)):
            if texte and not self.raccourcis.ajouter(texte, action):
                refuses.append(texte)
        return refuses

    # ------------------------------------------------------------ éjection
    def ejecter(self, p: Peripherique, demander: bool = True) -> None:
        if p.id in self.en_cours:
            return
        if demander and p.lecteur_de_cartes and self.reglages.demander_lecteur_cartes:
            if not self._confirmer_lecteur(p):
                return
        self.en_cours.add(p.id)

        def travail():
            try:
                r = peripheriques.ejecter(p)
            except Exception as exc:                    # noqa: BLE001
                r = peripheriques.Resultat(False, -1, f"{type(exc).__name__}: {exc}")
            self.fini.emit(p, r)

        threading.Thread(target=travail, daemon=True, name="pipit-ejection").start()

    def tout_ejecter(self) -> None:
        for p in self.lister():
            self.ejecter(p, demander=False)

    def _confirmer_lecteur(self, p: Peripherique) -> bool:
        boite = QtWidgets.QMessageBox()
        boite.setWindowTitle(systeme.NOM)
        boite.setIcon(QtWidgets.QMessageBox.Icon.Question)
        boite.setText(tr("lecteur.question", nom=self.nom(p),
                         lettres=", ".join(f"{l}:" for l in p.lettres) or "—"))
        case = QtWidgets.QCheckBox(tr("lecteur.ne_plus_demander"))
        boite.setCheckBox(case)
        oui = boite.addButton(tr("lecteur.ejecter"), QtWidgets.QMessageBox.ButtonRole.AcceptRole)
        boite.addButton(tr("dlg.annuler"), QtWidgets.QMessageBox.ButtonRole.RejectRole)
        boite.exec()
        if case.isChecked():
            self.reglages.demander_lecteur_cartes = False
            reglages.enregistrer(self.reglages)
        return boite.clickedButton() is oui

    def _resultat(self, p: Peripherique, r) -> None:
        self.en_cours.discard(p.id)
        self.actualiser()
        if r.ok:
            if self.reglages.notifier:
                self.tray.showMessage(tr("ejecte.titre"), tr("ejecte.texte", nom=self.nom(p)),
                                      self.icone, 4000)
            return
        self._refus(p, r)

    def raison(self, r) -> str:
        if r.veto == peripheriques.VETO_DROITS:
            return tr("veto.droits")
        if r.veto == peripheriques.VETO_SERVICE:
            return tr("veto.service", detail=r.detail or "?")
        if r.veto == peripheriques.VETO_APPLI:
            return tr("veto.appli", detail=r.detail or "?")
        if r.veto < 0:
            return tr("veto.erreur", detail=r.detail or str(r.veto))
        return tr("veto.ouvert")

    def _refus(self, p: Peripherique, r) -> None:
        boite = QtWidgets.QMessageBox()
        boite.setWindowTitle(systeme.NOM)
        boite.setIcon(QtWidgets.QMessageBox.Icon.Warning)
        boite.setText(tr("refus.titre", nom=self.nom(p)))
        lignes = [self.raison(r)]
        fermables = [b for b in r.bloqueurs if b.fermable]
        for b in r.bloqueurs:
            if b.explorateur:
                lignes.append(tr("refus.explorateur"))
            elif b.patienter:
                lignes.append(tr("refus.patienter", programme=b.programme))
            else:
                lignes.append(tr("refus.programme", programme=b.programme, pid=b.pid))
        if not r.bloqueurs and r.veto in (peripheriques.VETO_FICHIER_OUVERT, peripheriques.VETO_INCONNU,
                                          peripheriques.VETO_PERIPH):
            lignes.append(tr("refus.inconnu"))
        boite.setInformativeText("\n\n".join(lignes))
        fermer = None
        if fermables:
            noms = ", ".join(sorted({b.programme for b in fermables}))
            fermer = boite.addButton(tr("refus.fermer", programme=noms), QtWidgets.QMessageBox.ButtonRole.ActionRole)
        reessayer = boite.addButton(tr("refus.reessayer"), QtWidgets.QMessageBox.ButtonRole.AcceptRole)
        boite.addButton(tr("dlg.annuler"), QtWidgets.QMessageBox.ButtonRole.RejectRole)
        boite.exec()
        clic = boite.clickedButton()
        if fermer is not None and clic is fermer:
            for b in fermables:
                bloqueurs.fermer(b)
            QtCore.QTimer.singleShot(2500, lambda: self.ejecter(p, demander=False))
        elif clic is reessayer:
            self.ejecter(p, demander=False)

    # ------------------------------------------------------------ fenêtres
    def ouvrir_reglages(self) -> None:
        from .fenetre import FenetreReglages
        if self.fenetre is None:
            self.fenetre = FenetreReglages(self)
        self.fenetre.rafraichir()
        self.fenetre.show()
        self.fenetre.raise_()
        self.fenetre.activateWindow()

    def ouvrir_manuel(self) -> None:
        try:
            import interface_kit
            interface_kit.ouvrir_manuel([RACINE / "docs"], langue())
        except Exception:                               # noqa: BLE001
            pass

    def quitter(self) -> None:
        if self.raccourcis is not None:
            self.raccourcis.tout_retirer()
        self.tray.hide()
        self.app.quit()

    @property
    def version(self) -> str:
        return __version__
