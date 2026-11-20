"""L'icône près de l'horloge : menus, éjection (normale ou forcée), remontage, raccourcis.

Clic gauche : le menu d'éjection (comme USB Safely Remove). Clic droit : le même, plus
les outils (forcer, chercher qui bloque, ouvrir, réglages, quitter).
"""
from __future__ import annotations

import threading
from pathlib import Path

from PyQt6 import QtCore, QtGui, QtWidgets

from . import __version__, bloqueurs, peripheriques, reglages, systeme
from .i18n import langue, tr
from .modele import TYPES, Peripherique, taille_lisible

RACINE = Path(__file__).resolve().parent.parent
ICONES = Path(__file__).resolve().parent / "icones"


class _FiltreNatif(QtCore.QAbstractNativeEventFilter):
    """WM_HOTKEY (raccourcis) et WM_DEVICECHANGE (branchement, débranchement : on relit la
    liste tout de suite au lieu d'attendre le prochain sondage)."""

    def __init__(self, raccourcis, changement=None):
        super().__init__()
        self.raccourcis = raccourcis
        self.changement = changement

    def nativeEventFilter(self, type_evt, message):
        if type_evt == b"windows_generic_MSG":
            from ctypes import wintypes
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == 0x0312 and self.raccourcis is not None \
                    and self.raccourcis.message(msg.message, msg.wParam):
                return True, 0
            if msg.message == 0x0219 and self.changement is not None:     # WM_DEVICECHANGE
                self.changement()
        return False, 0


class Zone(QtCore.QObject):
    liste_prete = QtCore.pyqtSignal(object, object)   # (périphériques, éjectés encore branchés)
    fini = QtCore.pyqtSignal(object, object)          # (périphérique, Resultat)
    fini_admin = QtCore.pyqtSignal(str, object, object)   # (action, périphérique ou (id, nom), réponse)

    def __init__(self, app: QtWidgets.QApplication):
        super().__init__()
        self.app = app
        self.reglages = reglages.charger()
        self.fenetre = None
        self.en_cours: set[str] = set()
        self._derniers: list[Peripherique] = []
        self._attente: list[tuple[str, str]] = []
        logo = RACINE / "logo_32.png"
        self.icone = QtGui.QIcon(str(logo)) if logo.exists() else app.style().standardIcon(
            QtWidgets.QStyle.StandardPixmap.SP_DriveHDIcon)
        self._icones_type: dict[str, QtGui.QIcon] = {}
        self.tray = QtWidgets.QSystemTrayIcon(self.icone)
        self.menu = QtWidgets.QMenu()                  # clic gauche
        self.menu_complet = QtWidgets.QMenu()          # clic droit
        self.menu.aboutToShow.connect(lambda: self.construire_menu(self.menu, complet=False))
        self.menu_complet.aboutToShow.connect(lambda: self.construire_menu(self.menu_complet, complet=True))
        self.tray.setContextMenu(self.menu_complet)
        self.tray.activated.connect(self._clic)
        self.fini.connect(self._resultat)
        self.fini_admin.connect(self._resultat_admin)
        self.liste_prete.connect(self._liste_recue)
        self._lecture = threading.Lock()              # une seule lecture des périphériques à la fois
        self._etat_icone = None
        self._relire = QtCore.QTimer(self)            # WM_DEVICECHANGE arrive en rafale : on regroupe
        self._relire.setSingleShot(True)
        self._relire.setInterval(400)
        self._relire.timeout.connect(self.actualiser)
        # fenêtre invisible : reçoit WM_HOTKEY et donne le premier plan au menu
        self.ancre = QtWidgets.QWidget()
        self.ancre.setWindowFlags(QtCore.Qt.WindowType.Tool | QtCore.Qt.WindowType.FramelessWindowHint)
        self.ancre.resize(1, 1)
        self.raccourcis = None
        self.filtre = None
        self.appliquer_raccourcis()
        self.minuteur = QtCore.QTimer(self)              # filet de sécurité ; l'essentiel = WM_DEVICECHANGE
        self.minuteur.timeout.connect(self.actualiser)
        self.minuteur.start(10000)
        self._afficher_icone()
        self.tray.show()
        self.actualiser()

    # ------------------------------------------------------------ apparence
    def appliquer_theme(self) -> None:
        from . import style
        style.appliquer(self.app, self.reglages.theme)

    def icone_type(self, type_: str) -> QtGui.QIcon:
        if type_ not in self._icones_type:
            chemin = ICONES / f"{type_ if type_ in TYPES else 'autre'}.svg"
            self._icones_type[type_] = QtGui.QIcon(str(chemin))
        return self._icones_type[type_]

    def type_de(self, p: Peripherique) -> str:
        return self.reglages.types.get(p.materiel) or p.type

    def icone_de(self, p: Peripherique) -> QtGui.QIcon:
        perso = self.reglages.icones.get(p.materiel)
        if perso:
            chemin = systeme.dossier_donnees() / "icones" / perso
            if chemin.exists():
                return QtGui.QIcon(str(chemin))
        return self.icone_type(self.type_de(p))

    def _icone_zone(self, n: int) -> QtGui.QIcon:
        """Le logo, grisé quand il n'y a rien à retirer, avec le nombre de périphériques."""
        base = self.icone.pixmap(32, 32)
        if n == 0:
            return QtGui.QIcon(self.icone.pixmap(32, 32, QtGui.QIcon.Mode.Disabled))
        if not self.reglages.compteur:
            return QtGui.QIcon(base)
        image = base.toImage().convertToFormat(QtGui.QImage.Format.Format_ARGB32)
        p = QtGui.QPainter(image)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        p.setPen(QtCore.Qt.PenStyle.NoPen)
        p.setBrush(QtGui.QColor("#B5382B"))
        p.drawEllipse(QtCore.QRectF(15, 15, 17, 17))
        police = QtGui.QFont()
        police.setPixelSize(12)
        police.setBold(True)
        p.setFont(police)
        p.setPen(QtGui.QColor("white"))
        p.drawText(QtCore.QRectF(15, 15, 17, 17), QtCore.Qt.AlignmentFlag.AlignCenter, str(min(n, 9)))
        p.end()
        return QtGui.QIcon(QtGui.QPixmap.fromImage(image))

    # ------------------------------------------------------------ liste
    def lister(self, avec_masques: bool = False) -> list[Peripherique]:
        """Lecture directe (fenêtre des réglages, tests). L'icône, elle, lit en arrière-plan."""
        try:
            return peripheriques.lister(set(self.reglages.masques), self.reglages.internes_a_chaud,
                                        avec_masques=avec_masques, appareils=self.reglages.appareils,
                                        optiques=self.reglages.optiques)
        except Exception:                                # noqa: BLE001 — l'icône ne doit pas mourir
            return []

    def actualiser(self, attendre: bool = False) -> None:
        """Relit les périphériques dans un fil : un disque qui ne répond plus ne fige jamais
        l'icône. Pas de lecture pendant une éjection (Pipit ouvrirait le volume qu'il retire)."""
        if self.en_cours and not attendre:
            return
        pris = self._lecture.acquire(timeout=15) if attendre else self._lecture.acquire(blocking=False)
        if not pris:
            return

        def travail():
            try:
                perifs = self.lister()
                attente = peripheriques.en_attente_de_retrait()
            except Exception:                            # noqa: BLE001
                perifs, attente = [], []
            finally:
                self._lecture.release()
            self.liste_prete.emit(perifs, attente)

        fil = threading.Thread(target=travail, daemon=True, name="pipit-lecture")
        fil.start()
        if attendre:
            fil.join(15)
            QtWidgets.QApplication.processEvents()

    def demander_relecture(self) -> None:
        self._relire.start()

    def _liste_recue(self, perifs, attente) -> None:
        self._derniers, self._attente = perifs, attente
        self._afficher_icone()
        if self.fenetre is not None and self.fenetre.isVisible():
            self.fenetre.rafraichir_si_change()

    def _afficher_icone(self) -> None:
        n = len(self._derniers)
        etat = (n, self.reglages.compteur)
        if etat == self._etat_icone:                     # rien n'a changé : pas de redessin
            return
        self._etat_icone = etat
        self.tray.setIcon(self._icone_zone(n))
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
        elif not p.lettres and not any(d.appareil for d in p.disques):
            morceaux.append(tr("zone.vide"))
        if p.geste != "ejecter":
            morceaux.append("— " + tr(f"geste.{p.geste}"))
        return "  ".join(m for m in morceaux if m)

    # ------------------------------------------------------------ menus
    def construire_menu(self, menu: QtWidgets.QMenu, complet: bool) -> None:
        menu.clear()
        # liste déjà lue en arrière-plan ; on en relance une pour la prochaine ouverture
        self.demander_relecture()
        titre = menu.addAction(tr("zone.titre"))
        titre.setEnabled(False)
        if not self._derniers:
            menu.addAction(tr("zone.aucun")).setEnabled(False)
        for p in self._derniers:
            a = menu.addAction(self.icone_de(p), self.libelle(p))
            a.setToolTip(f"{tr('type.' + self.type_de(p))} — {p.bus} — {p.id}")
            a.setEnabled(p.id not in self.en_cours)
            a.triggered.connect(lambda _=False, p=p: self.ejecter(p))
        if len(self._derniers) > 1:
            menu.addSeparator()
            menu.addAction(tr("zone.tout"), self.tout_ejecter)
        if self._attente:
            menu.addSeparator()
            menu.addAction(tr("zone.remonter_titre")).setEnabled(False)
            for ident, nom in self._attente:
                a = menu.addAction(self.icone_type("autre"), tr("zone.remonter", nom=nom))
                a.setToolTip(ident)
                a.triggered.connect(lambda _=False, i=ident, n=nom: self.remonter(i, n))
        if complet:
            ejectables = [p for p in self._derniers if p.geste == "ejecter"]
            tiroirs = [p for p in self._derniers if p.geste == "tiroir"]
            if ejectables:
                menu.addSeparator()
                forcer = menu.addMenu(tr("zone.forcer"))
                coupables = menu.addMenu(tr("zone.coupables"))
                for p in ejectables:
                    forcer.addAction(self.icone_de(p), self.libelle(p), lambda p=p: self.forcer(p))
                    if p.lettres:
                        coupables.addAction(self.icone_de(p), self.libelle(p), lambda p=p: self.chercher_coupables(p))
                coupables.setEnabled(any(p.lettres for p in ejectables))
            if tiroirs:
                fermer = menu.addMenu(tr("zone.fermer_tiroir"))
                for p in tiroirs:
                    fermer.addAction(self.icone_de(p), self.libelle(p),
                                     lambda p=p: threading.Thread(target=peripheriques.fermer_tiroir, args=(p,),
                                                                  daemon=True).start())
            lettres = [(l, p) for p in self._derniers for l in p.lettres]
            if lettres:
                sous = menu.addMenu(tr("zone.ouvrir"))
                for l, p in lettres:
                    sous.addAction(self.icone_de(p), f"{l}:  {self.nom(p)}", lambda l=l: systeme.ouvrir_lecteur(l))
            menu.addSeparator()
            menu.addAction(tr("zone.reglages"), self.ouvrir_reglages)
            menu.addAction(tr("menu.manuel"), self.ouvrir_manuel)
            menu.addSeparator()
            menu.addAction(tr("menu.quitter"), self.quitter)
        else:
            menu.addSeparator()
            menu.addAction(tr("zone.plus"), lambda: self.montrer_menu(complet=True))

    def _clic(self, raison) -> None:
        if raison == QtWidgets.QSystemTrayIcon.ActivationReason.Trigger:   # un double clic = un seul menu
            self.montrer_menu()

    def montrer_menu(self, complet: bool = False) -> None:
        """Au curseur ; la fenêtre invisible prend le premier plan, sinon le menu
        ne se refermerait pas en cliquant ailleurs (règle connue de Windows)."""
        menu = self.menu_complet if complet else self.menu
        self.ancre.move(QtGui.QCursor.pos())
        self.ancre.show()
        self.ancre.activateWindow()
        self.ancre.raise_()
        menu.popup(QtGui.QCursor.pos())
        menu.activateWindow()
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
            self.filtre = _FiltreNatif(self.raccourcis, self.demander_relecture)
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
        if demander and p.geste == "ejecter" and p.lecteur_de_cartes and self.reglages.demander_lecteur_cartes:
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
        # « tout éjecter » ne doit pas ouvrir les tiroirs ni démonter les images ISO
        for p in self.lister():
            if p.geste == "ejecter":
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

    def _notifier_ok(self, p_nom: str) -> None:
        if self.reglages.notifier:
            self.tray.showMessage(tr("ejecte.titre"), tr("ejecte.texte", nom=p_nom), self.icone, 4000)

    def _resultat(self, p: Peripherique, r) -> None:
        self.en_cours.discard(p.id)
        self.actualiser()
        if r.ok:
            if r.veto == peripheriques.VETO_DEJA_RETIRE:   # débranché pendant que le menu était ouvert
                return
            if p.geste == "ejecter":
                self._notifier_ok(self.nom(p))
            elif self.reglages.notifier and p.geste == "demonter":
                self.tray.showMessage(tr("demonte.titre"), tr("demonte.texte", nom=self.nom(p)), self.icone, 3000)
            return
        if p.geste != "ejecter":
            QtWidgets.QMessageBox.warning(None, systeme.NOM, tr(f"echec.{p.geste}", nom=self.nom(p)))
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

    def _lignes_bloqueurs(self, liste) -> list[str]:
        lignes = []
        for b in liste:
            if b.explorateur:
                lignes.append(tr("refus.explorateur"))
            elif b.patienter:
                lignes.append(tr("refus.patienter", programme=b.programme))
            else:
                lignes.append(tr("refus.programme", programme=b.programme, pid=b.pid))
            for f in (b.fichiers or [])[:3]:
                lignes.append("    " + f)
            if len(b.fichiers or []) > 3:
                lignes.append("    " + tr("refus.autres", n=len(b.fichiers) - 3))
        return lignes

    def _refus(self, p: Peripherique, r) -> None:
        boite = QtWidgets.QMessageBox()
        boite.setWindowTitle(systeme.NOM)
        boite.setIcon(QtWidgets.QMessageBox.Icon.Warning)
        boite.setText(tr("refus.titre", nom=self.nom(p)))
        lignes = [self.raison(r)] + self._lignes_bloqueurs(r.bloqueurs)
        if not r.bloqueurs and r.veto in (peripheriques.VETO_FICHIER_OUVERT, peripheriques.VETO_INCONNU,
                                          peripheriques.VETO_PERIPH):
            lignes.append(tr("refus.inconnu"))
        boite.setInformativeText("\n".join(lignes))
        fermables = [b for b in r.bloqueurs if b.fermable]
        fermer = montrer = None
        if fermables:
            noms = ", ".join(sorted({b.programme for b in fermables}))
            montrer = boite.addButton(tr("refus.montrer", programme=fermables[0].programme),
                                      QtWidgets.QMessageBox.ButtonRole.ActionRole)
            fermer = boite.addButton(tr("refus.fermer", programme=noms), QtWidgets.QMessageBox.ButtonRole.ActionRole)
        chercher = None
        if p.lettres:
            chercher = boite.addButton(tr("refus.chercher_partout"), QtWidgets.QMessageBox.ButtonRole.ActionRole)
        forcer = boite.addButton(tr("refus.forcer"), QtWidgets.QMessageBox.ButtonRole.DestructiveRole)
        reessayer = boite.addButton(tr("refus.reessayer"), QtWidgets.QMessageBox.ButtonRole.AcceptRole)
        boite.addButton(tr("dlg.annuler"), QtWidgets.QMessageBox.ButtonRole.RejectRole)
        boite.exec()
        clic = boite.clickedButton()
        if montrer is not None and clic is montrer:
            bloqueurs.montrer(fermables[0].pid)
        elif fermer is not None and clic is fermer:
            for b in fermables:
                bloqueurs.fermer(b)
            QtCore.QTimer.singleShot(2500, lambda: self.ejecter(p, demander=False))
        elif chercher is not None and clic is chercher:
            self.chercher_coupables(p, partout=True)
        elif clic is forcer:
            self.forcer(p)
        elif clic is reessayer:
            self.ejecter(p, demander=False)

    # ------------------------------------------------------------ gestes administrateur
    def _admin(self, action: str, cible, appel) -> None:
        cle = cible.id if isinstance(cible, Peripherique) else cible[0]
        self.en_cours.add(cle)

        def travail():
            try:
                r = appel()
            except Exception as exc:                    # noqa: BLE001
                r = {"ok": False, "detail": f"{type(exc).__name__}: {exc}"}
            self.fini_admin.emit(action, cible, r)

        threading.Thread(target=travail, daemon=True, name=f"pipit-{action}").start()

    def forcer(self, p: Peripherique) -> None:
        boite = QtWidgets.QMessageBox()
        boite.setWindowTitle(systeme.NOM)
        boite.setIcon(QtWidgets.QMessageBox.Icon.Warning)
        boite.setText(tr("forcer.question", nom=self.nom(p)))
        boite.setInformativeText(tr("forcer.texte"))
        oui = boite.addButton(tr("forcer.oui"), QtWidgets.QMessageBox.ButtonRole.DestructiveRole)
        boite.addButton(tr("dlg.annuler"), QtWidgets.QMessageBox.ButtonRole.RejectRole)
        boite.exec()
        if boite.clickedButton() is oui:
            self._admin("forcer", p, lambda: peripheriques.forcer(p))

    def remonter(self, ident: str, nom: str) -> None:
        self._admin("remonter", (ident, nom), lambda: peripheriques.remonter(ident))

    def chercher_coupables(self, p: Peripherique, partout: bool = False) -> None:
        self._admin("coupables", p, lambda: {"liste": peripheriques.coupables(p, partout), "partout": partout})

    def _resultat_admin(self, action: str, cible, r: dict) -> None:
        cle = cible.id if isinstance(cible, Peripherique) else cible[0]
        self.en_cours.discard(cle)
        self.actualiser()
        if action == "forcer":
            if r.get("ok"):
                self._notifier_ok(self.nom(cible))
            else:
                self._echec_admin(r)
        elif action == "remonter":
            if r.get("ok"):
                if self.reglages.notifier:
                    self.tray.showMessage(tr("remonte.titre"), tr("remonte.texte", nom=cible[1]), self.icone, 4000)
            else:
                self._echec_admin(r, remontage=True)
        elif action == "coupables":
            self._montrer_coupables(cible, r.get("liste"), r.get("partout"))

    def _echec_admin(self, r: dict, remontage: bool = False) -> None:
        detail = r.get("detail", "")
        if detail == "uac_refuse":
            texte = tr("admin.uac_refuse")
        elif remontage:
            texte = tr("remonte.echec")
        else:
            texte = tr("forcer.echec", detail=r.get("detail") or r.get("veto") or "?")
        QtWidgets.QMessageBox.warning(None, systeme.NOM, texte)

    def _montrer_coupables(self, p: Peripherique, liste, partout: bool) -> None:
        boite = QtWidgets.QMessageBox()
        boite.setWindowTitle(systeme.NOM)
        boite.setIcon(QtWidgets.QMessageBox.Icon.Information)
        boite.setText(tr("coupables.titre", nom=self.nom(p)))
        if liste is None:
            texte = tr("coupables.inconnu")
        elif not liste:
            texte = tr("coupables.aucun_partout") if partout else tr("coupables.aucun")
        else:
            lignes = []
            for c in liste:
                lignes.append(tr("refus.programme", programme=c.programme, pid=c.pid))
                lignes += ["    " + f for f in c.fichiers[:5]]
                if len(c.fichiers) > 5:
                    lignes.append("    " + tr("refus.autres", n=len(c.fichiers) - 5))
            texte = "\n".join(lignes)
        boite.setInformativeText(texte)
        ejecter = boite.addButton(tr("coupables.ejecter"), QtWidgets.QMessageBox.ButtonRole.AcceptRole)
        partout_b = None
        if not partout:
            partout_b = boite.addButton(tr("refus.chercher_partout"), QtWidgets.QMessageBox.ButtonRole.ActionRole)
        boite.addButton(tr("fen.fermer"), QtWidgets.QMessageBox.ButtonRole.RejectRole)
        boite.exec()
        if boite.clickedButton() is ejecter:
            self.ejecter(p, demander=False)
        elif partout_b is not None and boite.clickedButton() is partout_b:
            self.chercher_coupables(p, partout=True)

    # ------------------------------------------------------------ fin de session
    def fin_de_session(self, gestionnaire) -> None:
        """Rappel des périphériques encore branchés (option, désactivée par défaut)."""
        if not self.reglages.rappel_fermeture:
            return
        restants = self.lister()
        if not restants or not gestionnaire.allowsInteraction():
            return
        boite = QtWidgets.QMessageBox()
        boite.setWindowTitle(systeme.NOM)
        boite.setIcon(QtWidgets.QMessageBox.Icon.Question)
        boite.setText(tr("oubli.titre"))
        boite.setInformativeText("\n".join(self.libelle(p) for p in restants))
        tout = boite.addButton(tr("oubli.ejecter"), QtWidgets.QMessageBox.ButtonRole.AcceptRole)
        boite.addButton(tr("oubli.continuer"), QtWidgets.QMessageBox.ButtonRole.RejectRole)
        boite.exec()
        gestionnaire.release()
        if boite.clickedButton() is tout:
            for p in restants:                     # vite : pas de recherche de coupables à l'arrêt
                if p.geste == "ejecter":
                    peripheriques.ejecter(p, essais=1, chercher=False)

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
