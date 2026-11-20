"""Fenêtre des réglages : périphériques (nom, masqués), raccourcis, options, aide."""
from __future__ import annotations

import threading

from PyQt6 import QtCore, QtGui, QtWidgets

from . import __version__, reglages, systeme
from .i18n import definir_langue, langue, tr
from .modele import taille_lisible
from .modele import TYPES
from .raccourci import CHOIX_MENU, CHOIX_TOUT

COL_LETTRES, COL_ICONE, COL_NOM, COL_TYPE, COL_MATERIEL, COL_TAILLE, COL_BUS, COL_MASQUE = range(8)


class FenetreReglages(QtWidgets.QWidget):
    _maj_signal = QtCore.pyqtSignal(object, bool)

    def __init__(self, zone):
        super().__init__()
        self.zone = zone
        self.qsettings = QtCore.QSettings("ARP273-ROSE", systeme.NOM)
        self.setWindowIcon(zone.icone)
        self.resize(1000, 720)
        self._maj_signal.connect(self._resultat_maj)
        self._contenu = None
        QtWidgets.QVBoxLayout(self).setContentsMargins(0, 0, 0, 0)
        self._construire()

    @property
    def r(self) -> reglages.Reglages:
        return self.zone.reglages

    # ------------------------------------------------------------ construction
    def _construire(self) -> None:
        # tout le contenu vit dans un widget remplaçable : on jette l'ancien plus tard
        # (deleteLater), jamais pendant qu'un de ses signaux est en cours d'émission
        if self._contenu is not None:
            self.layout().removeWidget(self._contenu)
            self._contenu.hide()
            self._contenu.deleteLater()
        self._contenu = QtWidgets.QWidget(self)
        self.layout().addWidget(self._contenu)
        self.setWindowTitle(tr("fen.titre", version=__version__))
        lo = QtWidgets.QVBoxLayout(self._contenu)

        titre = QtWidgets.QLabel(tr("fen.entete"))
        titre.setProperty("role", "titre")
        lo.addWidget(titre)
        sous = QtWidgets.QLabel(tr("fen.sous_titre"))
        sous.setProperty("role", "sous-titre")
        sous.setWordWrap(True)
        lo.addWidget(sous)

        # --- périphériques
        g = QtWidgets.QGroupBox(tr("fen.peripheriques"))
        gl = QtWidgets.QVBoxLayout(g)
        self.table = QtWidgets.QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels([tr("col.lettres"), tr("col.icone"), tr("col.nom"), tr("col.type"),
                                              tr("col.materiel"), tr("col.taille"), tr("col.bus"),
                                              tr("col.masquer")])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.itemChanged.connect(self._modif_table)
        gl.addWidget(self.table)
        aide = QtWidgets.QLabel(tr("fen.peripheriques.aide"))
        aide.setWordWrap(True)
        aide.setProperty("role", "sous-titre")
        gl.addWidget(aide)
        lo.addWidget(g, 1)

        # --- raccourcis et options
        bas = QtWidgets.QHBoxLayout()
        gr = QtWidgets.QGroupBox(tr("fen.raccourcis"))
        fl = QtWidgets.QFormLayout(gr)
        self.cb_menu = self._combo(CHOIX_MENU, self.r.raccourci_menu)
        self.cb_tout = self._combo(CHOIX_TOUT, self.r.raccourci_tout)
        fl.addRow(tr("fen.raccourci_menu"), self.cb_menu)
        fl.addRow(tr("fen.raccourci_tout"), self.cb_tout)
        self.etat_raccourcis = QtWidgets.QLabel("")
        self.etat_raccourcis.setWordWrap(True)
        fl.addRow(self.etat_raccourcis)
        self.cb_menu.currentIndexChanged.connect(self._modif_raccourcis)
        self.cb_tout.currentIndexChanged.connect(self._modif_raccourcis)
        gauche = QtWidgets.QVBoxLayout()
        gauche.addWidget(gr)
        ga = QtWidgets.QGroupBox(tr("fen.assistant"))
        al = QtWidgets.QVBoxLayout(ga)
        self.etat_assistant = QtWidgets.QLabel("")
        self.etat_assistant.setWordWrap(True)
        al.addWidget(self.etat_assistant)
        self.b_assistant = QtWidgets.QPushButton("")
        self.b_assistant.clicked.connect(self._basculer_assistant)
        al.addWidget(self.b_assistant)
        gauche.addWidget(ga)
        gauche.addStretch(1)
        bas.addLayout(gauche, 1)
        self._etat_assistant()

        go = QtWidgets.QGroupBox(tr("fen.options"))
        ol = QtWidgets.QVBoxLayout(go)
        self.c_notifier = self._case(ol, tr("opt.notifier"), self.r.notifier, "notifier")
        self.c_lecteur = self._case(ol, tr("opt.lecteur"), self.r.demander_lecteur_cartes,
                                    "demander_lecteur_cartes")
        self.c_internes = self._case(ol, tr("opt.internes"), self.r.internes_a_chaud, "internes_a_chaud")
        self.c_internes.setToolTip(tr("opt.internes.aide"))
        self.c_appareils = self._case(ol, tr("opt.appareils"), self.r.appareils, "appareils")
        self.c_optiques = self._case(ol, tr("opt.optiques"), self.r.optiques, "optiques")
        self.c_compteur = self._case(ol, tr("opt.compteur"), self.r.compteur, "compteur")
        self.c_rappel = self._case(ol, tr("opt.rappel"), self.r.rappel_fermeture, "rappel_fermeture")
        self.c_rappel.setToolTip(tr("opt.rappel.aide"))
        self.c_demarrage = QtWidgets.QCheckBox(tr("opt.demarrage"))
        self.c_demarrage.setChecked(systeme.lance_avec_windows())
        self.c_demarrage.setEnabled(systeme.WINDOWS)
        self.c_demarrage.toggled.connect(systeme.lancer_avec_windows)
        ol.addWidget(self.c_demarrage)
        self.c_rapports = QtWidgets.QCheckBox(tr("menu.rapports_auto"))
        try:
            import reporting
            self.c_rapports.setChecked(reporting.consentement() is True)
            self.c_rapports.toggled.connect(lambda c: reporting.definir_consentement(bool(c)))
        except Exception:                               # noqa: BLE001
            self.c_rapports.setEnabled(False)
        ol.addWidget(self.c_rapports)
        ligne = QtWidgets.QHBoxLayout()
        ligne.addWidget(QtWidgets.QLabel(tr("menu.langue")))
        self.cb_langue = QtWidgets.QComboBox()
        for code in ("auto", "fr", "en"):
            self.cb_langue.addItem(tr(f"menu.langue.{code}"), code)
        self.cb_langue.setCurrentIndex(max(0, self.cb_langue.findData(
            self.qsettings.value("langue", "auto", type=str))))
        self.cb_langue.currentIndexChanged.connect(self._changer_langue)
        ligne.addWidget(self.cb_langue, 1)
        ol.addLayout(ligne)
        ligne = QtWidgets.QHBoxLayout()
        ligne.addWidget(QtWidgets.QLabel(tr("opt.theme")))
        self.cb_theme = QtWidgets.QComboBox()
        for code in ("sombre", "clair"):
            self.cb_theme.addItem(tr(f"theme.{code}"), code)
        self.cb_theme.setCurrentIndex(max(0, self.cb_theme.findData(self.r.theme)))
        self.cb_theme.currentIndexChanged.connect(self._changer_theme)
        ligne.addWidget(self.cb_theme, 1)
        ol.addLayout(ligne)
        bas.addWidget(go, 1)
        lo.addLayout(bas)

        # --- boutons
        bl = QtWidgets.QHBoxLayout()
        for texte, action in ((tr("menu.manuel"), self.zone.ouvrir_manuel),
                              (tr("menu.maj"), lambda: self.verifier_maj(manuel=True)),
                              (tr("menu.signaler"), self._signaler),
                              (tr("menu.a_propos"), self._a_propos)):
            b = QtWidgets.QPushButton(texte)
            b.clicked.connect(action)
            bl.addWidget(b)
        bl.addStretch(1)
        fermer = QtWidgets.QPushButton(tr("fen.fermer"))
        fermer.setProperty("role", "principal")
        fermer.clicked.connect(self.close)
        bl.addWidget(fermer)
        lo.addLayout(bl)
        self._modif_raccourcis(appliquer=False)

    def _combo(self, choix: list[str], actuel: str) -> QtWidgets.QComboBox:
        cb = QtWidgets.QComboBox()
        valeurs = list(choix) + ([actuel] if actuel and actuel not in choix else [])
        for v in valeurs:
            cb.addItem(v or tr("fen.aucun"), v)
        cb.setCurrentIndex(max(0, cb.findData(actuel)))
        return cb

    def _case(self, lo, texte: str, valeur: bool, attribut: str) -> QtWidgets.QCheckBox:
        c = QtWidgets.QCheckBox(texte)
        c.setChecked(valeur)

        def changer(coche):
            setattr(self.r, attribut, bool(coche))
            reglages.enregistrer(self.r)
            self.rafraichir()
            self.zone.actualiser()
        c.toggled.connect(changer)
        lo.addWidget(c)
        return c

    # ------------------------------------------------------------ périphériques
    def rafraichir(self) -> None:
        self._remplissage = True
        perifs = self.zone.lister(avec_masques=True)
        self.table.setRowCount(len(perifs))
        for i, p in enumerate(perifs):
            valeurs = {COL_LETTRES: ", ".join(f"{l}:" for l in p.lettres),
                       COL_NOM: self.zone.nom(p), COL_MATERIEL: p.nom,
                       COL_TAILLE: taille_lisible(p.taille, langue()), COL_BUS: p.bus}
            for col, texte in valeurs.items():
                item = QtWidgets.QTableWidgetItem(texte)
                if col != COL_NOM:
                    item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
                item.setData(QtCore.Qt.ItemDataRole.UserRole, p.materiel)
                item.setToolTip(p.id)
                self.table.setItem(i, col, item)
            case = QtWidgets.QTableWidgetItem()
            case.setFlags(QtCore.Qt.ItemFlag.ItemIsUserCheckable | QtCore.Qt.ItemFlag.ItemIsEnabled)
            case.setCheckState(QtCore.Qt.CheckState.Checked if p.materiel in self.r.masques
                               else QtCore.Qt.CheckState.Unchecked)
            case.setData(QtCore.Qt.ItemDataRole.UserRole, p.materiel)
            self.table.setItem(i, COL_MASQUE, case)
            # icône : bouton avec un petit menu (choisir une image, revenir à l'icône du type)
            bouton = QtWidgets.QToolButton()
            bouton.setIcon(self.zone.icone_de(p))
            bouton.setIconSize(QtCore.QSize(24, 24))
            bouton.setAutoRaise(True)
            bouton.setToolTip(tr("icone.aide"))
            bouton.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
            m = QtWidgets.QMenu(bouton)
            m.addAction(tr("icone.choisir"), lambda mat=p.materiel: self.choisir_icone(mat))
            m.addAction(tr("icone.defaut"), lambda mat=p.materiel: self.icone_par_defaut(mat))
            bouton.setMenu(m)
            self.table.setCellWidget(i, COL_ICONE, bouton)
            # type : deviné, corrigeable
            cb = QtWidgets.QComboBox()
            cb.addItem(tr("type.auto", type=tr("type." + p.type)), "")
            for t in TYPES:
                cb.addItem(self.zone.icone_type(t), tr("type." + t), t)
            cb.setCurrentIndex(max(0, cb.findData(self.r.types.get(p.materiel, ""))))
            cb.currentIndexChanged.connect(lambda _i, cb=cb, mat=p.materiel: self._changer_type(mat, cb.currentData()))
            self.table.setCellWidget(i, COL_TYPE, cb)
        self.table.resizeColumnsToContents()
        entete = self.table.horizontalHeader()
        entete.setSectionResizeMode(COL_NOM, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        entete.setSectionResizeMode(COL_MATERIEL, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self._remplissage = False

    def _changer_type(self, materiel: str, type_: str) -> None:
        if type_:
            self.r.types[materiel] = type_
        else:
            self.r.types.pop(materiel, None)
        reglages.enregistrer(self.r)
        QtCore.QTimer.singleShot(0, self.rafraichir)

    def choisir_icone(self, materiel: str, chemin: str | None = None) -> None:
        """Image au choix (PNG, ICO, SVG, JPG), copiée en 64 px dans le dossier des données."""
        if chemin is None:
            chemin, _f = QtWidgets.QFileDialog.getOpenFileName(
                self, tr("icone.choisir"), "", tr("icone.filtre") + " (*.png *.ico *.svg *.jpg *.jpeg *.bmp)")
        if not chemin:
            return
        image = QtGui.QIcon(chemin).pixmap(64, 64)
        if image.isNull():
            QtWidgets.QMessageBox.warning(self, systeme.NOM, tr("icone.illisible"))
            return
        import hashlib
        dossier = systeme.dossier_donnees() / "icones"
        dossier.mkdir(parents=True, exist_ok=True)
        nom = hashlib.sha1(materiel.encode("utf-8")).hexdigest()[:16] + ".png"
        image.save(str(dossier / nom), "PNG")
        self.r.icones[materiel] = nom
        reglages.enregistrer(self.r)
        self.rafraichir()
        self.zone.actualiser()

    def icone_par_defaut(self, materiel: str) -> None:
        self.r.icones.pop(materiel, None)
        reglages.enregistrer(self.r)
        self.rafraichir()

    def _modif_table(self, item: QtWidgets.QTableWidgetItem) -> None:
        if getattr(self, "_remplissage", True):
            return
        materiel = item.data(QtCore.Qt.ItemDataRole.UserRole)
        if item.column() == COL_MASQUE:
            masques = set(self.r.masques)
            if item.checkState() == QtCore.Qt.CheckState.Checked:
                masques.add(materiel)
            else:
                masques.discard(materiel)
            self.r.masques = sorted(masques)
        elif item.column() == COL_NOM:
            texte = item.text().strip()
            origine = self.table.item(item.row(), COL_MATERIEL).text()
            if texte and texte != origine:
                self.r.noms[materiel] = texte
            else:
                self.r.noms.pop(materiel, None)
        else:
            return
        reglages.enregistrer(self.r)
        self.zone.actualiser()

    # ------------------------------------------------------------ assistant administrateur
    def _etat_assistant(self) -> None:
        from . import assistant
        present = assistant.installe()
        self.etat_assistant.setText(tr("assistant.present") if present else tr("assistant.absent"))
        self.b_assistant.setText(tr("assistant.retirer") if present else tr("assistant.installer"))
        self.b_assistant.setEnabled(systeme.WINDOWS)

    def _basculer_assistant(self) -> None:
        from . import assistant
        if assistant.installe():
            assistant.desinstaller()
        elif not assistant.installer():
            QtWidgets.QMessageBox.warning(self, systeme.NOM, tr("admin.uac_refuse"))
        self._etat_assistant()

    def _changer_theme(self) -> None:
        self.r.theme = self.cb_theme.currentData() or "sombre"
        reglages.enregistrer(self.r)
        self.zone.appliquer_theme()

    # ------------------------------------------------------------ raccourcis, langue
    def _modif_raccourcis(self, *_args, appliquer: bool = True) -> None:
        if appliquer:
            self.r.raccourci_menu = self.cb_menu.currentData() or ""
            self.r.raccourci_tout = self.cb_tout.currentData() or ""
            reglages.enregistrer(self.r)
        refuses = self.zone.appliquer_raccourcis() if appliquer else getattr(self, "_refuses", [])
        self._refuses = refuses
        self.etat_raccourcis.setText(tr("fen.raccourci_pris", raccourcis=", ".join(refuses)) if refuses else "")

    def _changer_langue(self) -> None:
        code = self.cb_langue.currentData()
        self.qsettings.setValue("langue", code)
        definir_langue(code if code in ("fr", "en") else None)
        QtCore.QTimer.singleShot(0, self._reconstruire)

    def _reconstruire(self) -> None:
        self._construire()
        self.rafraichir()
        self.zone.actualiser()

    # ------------------------------------------------------------ aide
    def _a_propos(self) -> None:
        boite = QtWidgets.QMessageBox(self)
        boite.setWindowTitle(tr("menu.a_propos"))
        logo = systeme_logo()
        if logo is not None:
            boite.setIconPixmap(logo)
        boite.setText(tr("a_propos.texte", version=__version__))
        boite.exec()

    def verifier_maj(self, manuel: bool = False) -> None:
        def travail():
            try:
                import updater
                info = updater.check(__version__)
            except Exception:                           # noqa: BLE001
                info = None
            self._maj_signal.emit(info, manuel)
        threading.Thread(target=travail, daemon=True, name="pipit-maj").start()

    def _resultat_maj(self, info, manuel: bool) -> None:
        if not info:
            if manuel:
                QtWidgets.QMessageBox.information(self, tr("maj.titre"), tr("maj.a_jour", version=__version__))
            return
        try:
            import updater
            installe = bool(updater.is_packaged())
            page = f"https://github.com/{updater.REPO}/releases/latest"
            notes = updater.notes_dans_la_langue((info.get("notes") or "").strip(), langue())
        except Exception:                               # noqa: BLE001
            installe, page, notes = False, "", ""
        boite = QtWidgets.QMessageBox(self)
        boite.setWindowTitle(tr("maj.titre"))
        boite.setText(tr("maj.dispo", nouvelle=info["version"], version=__version__))
        if notes:
            boite.setDetailedText(notes[:4000])
        oui = boite.addButton(tr("maj.installer") if installe else tr("maj.page"),
                              QtWidgets.QMessageBox.ButtonRole.AcceptRole)
        boite.addButton(tr("maj.plus_tard"), QtWidgets.QMessageBox.ButtonRole.RejectRole)
        boite.exec()
        if boite.clickedButton() is not oui:
            return
        if not installe:
            if page:
                QtGui.QDesktopServices.openUrl(QtCore.QUrl(page))
            return
        self._poser_maj(info)

    def _poser_maj(self, info: dict) -> None:
        import updater
        dlg = QtWidgets.QProgressDialog(tr("maj.telechargement"), None, 0, 100, self)
        dlg.setWindowTitle(tr("maj.titre"))
        dlg.setCancelButton(None)
        dlg.setMinimumDuration(0)
        etat = {"fait": 0, "total": 0, "fini": False, "erreur": None, "pose": False}

        def prog(fait, total):
            etat["fait"], etat["total"] = fait, total

        def travail():
            try:
                etat["pose"] = bool(updater.download_and_apply(info, progress=prog))
            except Exception as exc:                    # noqa: BLE001
                etat["erreur"] = exc
            finally:
                etat["fini"] = True

        threading.Thread(target=travail, daemon=True, name="pipit-maj-pose").start()
        minuteur = QtCore.QTimer(self)
        minuteur.setInterval(100)

        def tic():
            if not etat["fini"]:
                if etat["total"] > 0:
                    dlg.setValue(min(99, etat["fait"] * 100 // etat["total"]))
                return
            minuteur.stop()
            dlg.close()
            if etat["erreur"] is not None or not etat["pose"]:
                QtWidgets.QMessageBox.warning(self, tr("maj.titre"),
                                              tr("maj.echec", erreur=str(etat["erreur"] or "?")))
                return
            QtWidgets.QMessageBox.information(self, tr("maj.titre"), tr("maj.redemarre"))
            try:
                updater.restart()
            finally:
                self.zone.quitter()

        minuteur.timeout.connect(tic)
        minuteur.start()
        self._minuteur_maj = minuteur

    def _signaler(self) -> None:
        try:
            import reporting
        except Exception:                               # noqa: BLE001
            return
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle(tr("signal.titre"))
        dlg.resize(540, 340)
        lo = QtWidgets.QVBoxLayout(dlg)
        lo.addWidget(QtWidgets.QLabel(tr("signal.invite")))
        texte = QtWidgets.QPlainTextEdit()
        texte.setPlaceholderText(tr("signal.exemple"))
        lo.addWidget(texte)
        boutons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok
                                             | QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        boutons.button(QtWidgets.QDialogButtonBox.StandardButton.Ok).setText(tr("signal.envoyer"))
        boutons.button(QtWidgets.QDialogButtonBox.StandardButton.Cancel).setText(tr("dlg.annuler"))
        boutons.accepted.connect(dlg.accept)
        boutons.rejected.connect(dlg.reject)
        lo.addWidget(boutons)
        if dlg.exec() != QtWidgets.QDialog.DialogCode.Accepted or not texte.toPlainText().strip():
            return
        accord = reporting.consentement()
        if accord is not True:
            reporting.definir_consentement(True)
        rapport = reporting.envoyer("manuel", description=texte.toPlainText().strip(), version=__version__)
        if accord is not True:
            reporting.definir_consentement(bool(accord))
        chemin = None
        try:
            chemin = reporting.paquet_local(rapport, None)
        except Exception:                               # noqa: BLE001
            pass
        QtWidgets.QMessageBox.information(
            self, tr("signal.merci"),
            tr("signal.parti") if rapport.get("transmis", True) and not chemin else tr("signal.local", chemin=chemin))

    def closeEvent(self, ev) -> None:                   # fermer = cacher ; l'icône reste
        ev.ignore()
        self.hide()


def systeme_logo():
    from pathlib import Path
    chemin = Path(__file__).resolve().parent.parent / "logo_128.png"
    return QtGui.QPixmap(str(chemin)) if chemin.exists() else None
