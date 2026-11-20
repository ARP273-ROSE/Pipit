#!/usr/bin/env python3
"""Lanceur de Pipit — retirer une clé ou un disque USB sans risque.

    python run.py              icône près de l'horloge (+ réglages au premier lancement)
    python run.py --discret    icône seule (lancement avec Windows)
    python run.py --lister     liste les périphériques retirables, sans rien éjecter
    python run.py --ejecter E  éjecte le périphérique qui porte la lettre E:
    python run.py --assistant  (interne) gestes administrateur demandés par l'icône

Branchement du kit commun : rapports d'incident (plantage Python, crash
natif, gel), accord au premier lancement, verrou nommé lu par l'installeur,
vérification silencieuse des mises à jour.
"""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) or ".")

NOM = "Pipit"
_fichier_faulthandler = None


def _dossier_donnees() -> Path:
    from pipit import systeme
    return systeme.dossier_donnees()


def _demarrer_rapports() -> None:
    dossier = _dossier_donnees()
    trace_native = dossier / "_crash_natif.log"
    try:
        import reporting
        from pipit import __version__
        reporting.init(dossier, application="pipit", version=__version__)
        reporting.relever_crash_natif(trace_native)
        reporting.reprendre_file_en_fond()
    except Exception:
        pass
    try:
        import faulthandler
        global _fichier_faulthandler
        _fichier_faulthandler = open(trace_native, "w", encoding="utf-8")
        faulthandler.enable(file=_fichier_faulthandler, all_threads=True)
    except Exception:
        pass


def _premier_lancement(zone) -> None:
    """Accord pour les rapports, puis lancement avec Windows : deux questions, une seule fois."""
    from PyQt6 import QtWidgets
    from pipit import reglages, systeme
    from pipit.i18n import tr
    try:
        import reporting
        premier = reporting.consentement() is None
        if premier:
            boite = QtWidgets.QMessageBox()
            boite.setWindowTitle(NOM)
            boite.setIcon(QtWidgets.QMessageBox.Icon.Question)
            boite.setText(tr("accord.titre"))
            boite.setInformativeText(tr("accord.texte"))
            oui = boite.addButton(tr("dlg.oui"), QtWidgets.QMessageBox.ButtonRole.AcceptRole)
            boite.addButton(tr("dlg.non"), QtWidgets.QMessageBox.ButtonRole.RejectRole)
            boite.exec()
            reporting.definir_consentement(boite.clickedButton() is oui)
        reporting.signaler_demarrage(premier=premier)
    except Exception:
        pass
    if not zone.reglages.demarrage_propose and systeme.WINDOWS:
        zone.reglages.demarrage_propose = True
        reglages.enregistrer(zone.reglages)
        if not systeme.lance_avec_windows():
            boite = QtWidgets.QMessageBox()
            boite.setWindowTitle(NOM)
            boite.setIcon(QtWidgets.QMessageBox.Icon.Question)
            boite.setText(tr("demarrage.question"))
            boite.setInformativeText(tr("demarrage.question.texte"))
            oui = boite.addButton(tr("dlg.oui"), QtWidgets.QMessageBox.ButtonRole.AcceptRole)
            boite.addButton(tr("dlg.non"), QtWidgets.QMessageBox.ButtonRole.RejectRole)
            boite.exec()
            if boite.clickedButton() is oui:
                systeme.lancer_avec_windows(True)


def _rapport_crash(exc: BaseException) -> None:
    """Une application sans console : sans ce filet, une erreur au démarrage
    fermerait le programme sans rien montrer."""
    import datetime
    import traceback
    texte = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    entete = f"{NOM} — erreur au démarrage — {datetime.datetime.now():%Y-%m-%d %H:%M:%S}\n"
    chemin = _dossier_donnees() / "pipit-erreur.log"
    try:
        with open(chemin, "a", encoding="utf-8") as fh:
            fh.write(entete + texte + "\n")
    except OSError:
        chemin = "(journal impossible à écrire)"
    sys.stderr.write(entete + texte) if sys.stderr else None
    try:
        import reporting
        reporting.signaler_plantage(texte)
    except Exception:
        pass
    try:
        from PyQt6 import QtWidgets
        app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])  # noqa: F841
        from pipit.i18n import tr
        QtWidgets.QMessageBox.critical(
            None, NOM, tr("demarrage.echec", erreur=f"{type(exc).__name__}: {exc}", chemin=chemin))
    except Exception:
        pass


def _verifier() -> int:
    """--check : l'application et ses dépendances se chargent (lancé par la
    construction des paquets avec l'interpréteur embarqué ; aucune fenêtre)."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PyQt6 import QtWidgets
        app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv[:1])
        import interface_kit  # noqa: F401
        import reporting  # noqa: F401
        import updater  # noqa: F401
        from pipit import fenetre, peripheriques, style, zone  # noqa: F401
        if sys.platform == "win32":
            from pipit import disques_windows  # noqa: F401
        style.appliquer(app)
        del app
    except Exception as exc:
        print(f"Pipit : ECHEC / FAILED -- {type(exc).__name__}: {exc}")
        return 1
    print("Pipit : OK")
    return 0


def _console() -> None:
    for flux in (sys.stdout, sys.stderr):        # console Windows : pas de caractère illisible
        try:
            flux.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _lister(tout: bool) -> int:
    _console()
    from pipit import peripheriques, reglages
    from pipit.i18n import langue
    from pipit.modele import regrouper, taille_lisible
    if tout:
        for d in peripheriques.tous_les_disques():
            print(f"disque {d.numero}: {d.nom} | bus={d.bus} | {taille_lisible(d.taille, langue())} | "
                  f"lettres={','.join(d.lettres) or '-'} | systeme={d.systeme} | ejectable={d.id_ejectable or '-'}")
        print()
        groupes = regrouper(peripheriques.tous_les_disques())
        print(f"{len(groupes)} groupe(s) éjectable(s)")
    r = reglages.charger()
    for p in peripheriques.lister(set(r.masques), r.internes_a_chaud, avec_masques=True):
        masque = " [masqué]" if p.materiel in {m.upper() for m in r.masques} else ""
        print(f"{','.join(l + ':' for l in p.lettres) or '-'}\t{p.nom}\t{p.type}\t{p.bus}\t"
              f"{taille_lisible(p.taille, langue())}\t{p.id}{masque}")
    if tout:
        for ident, nom in peripheriques.en_attente_de_retrait():
            print(f"[éjecté, encore branché] {nom}\t{ident}")
    return 0


def _ejecter(lettre: str) -> int:
    _console()
    from pipit import peripheriques, reglages
    from pipit.i18n import tr
    r = reglages.charger()
    lettre = lettre.strip(":\\").upper()
    for p in peripheriques.lister(set(r.masques), r.internes_a_chaud, avec_masques=True):
        if lettre in p.lettres:
            res = peripheriques.ejecter(p)
            if res.ok:
                print(tr("ejecte.texte", nom=p.nom))
                return 0
            print(tr("refus.titre", nom=p.nom), f"(veto {res.veto} {res.detail})")
            for b in res.bloqueurs:
                print(tr("refus.programme", programme=b.programme, pid=b.pid))
            return 2
    print(f"{lettre}: ?")
    return 1


def main() -> int:
    if "--check" in sys.argv[1:]:
        return _verifier()
    if "--assistant" in sys.argv[1:]:
        # assistant administrateur (tâche planifiée ou fenêtre UAC) : traite les demandes, puis s'arrête
        from pipit import assistant
        return assistant.executer(sys.argv[sys.argv.index("--assistant") + 1:])
    from pipit.i18n import definir_langue, tr
    ap = argparse.ArgumentParser(description=tr("cli.description"))
    ap.add_argument("--discret", action="store_true", help="tray icon only / icône seule")
    ap.add_argument("--lister", "--list", action="store_true", help="list removable devices / lister")
    ap.add_argument("--tout", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--ejecter", "--eject", metavar="LETTRE", help="eject the drive / éjecter le lecteur")
    ap.add_argument("--lang", choices=["fr", "en"], help="interface language / langue")
    from pipit import __version__
    ap.add_argument("--version", action="version", version=f"Pipit {__version__}")
    args = ap.parse_args()

    choix = args.lang
    if not choix:
        try:
            from PyQt6 import QtCore
            choix = QtCore.QSettings("ARP273-ROSE", NOM).value("langue", "auto", type=str)
        except ImportError:                    # --lister / --ejecter marchent sans Qt
            choix = "auto"
    definir_langue(choix if choix in ("fr", "en") else None)

    if args.lister:
        return _lister(args.tout)
    if args.ejecter:
        return _ejecter(args.ejecter)

    from PyQt6 import QtCore
    if sys.platform == "win32":
        import ctypes
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        mutex = k32.CreateMutexW(None, False, f"{NOM}EnCours")
        if ctypes.get_last_error() == 183:                       # ERROR_ALREADY_EXISTS : déjà lancé
            return 0
    else:
        mutex = None

    _demarrer_rapports()
    from PyQt6 import QtGui, QtWidgets
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName(NOM)
    app.setQuitOnLastWindowClosed(False)                       # l'icône vit sans fenêtre
    app._mutex_installeur = mutex
    from pipit import reglages, style
    style.appliquer(app, reglages.charger().theme)
    icone = Path(__file__).resolve().parent / "logo.png"
    if icone.exists():
        app.setWindowIcon(QtGui.QIcon(str(icone)))
    if not QtWidgets.QSystemTrayIcon.isSystemTrayAvailable():
        QtWidgets.QMessageBox.critical(None, NOM, tr("demarrage.sans_zone"))
        return 1

    from pipit.zone import Zone
    zone = Zone(app)
    app.commitDataRequest.connect(zone.fin_de_session)
    premier = not zone.reglages.demarrage_propose
    QtCore.QTimer.singleShot(800, lambda: _premier_lancement(zone))
    if premier or not args.discret:
        QtCore.QTimer.singleShot(1500, zone.ouvrir_reglages)
    try:
        import updater
        if updater.is_packaged():
            QtCore.QTimer.singleShot(8000, lambda: _maj_silencieuse(zone))
    except Exception:
        pass
    try:
        import reporting
        vigie = reporting.Vigie(seuil=10.0, periode=2.0)
        vigie.demarrer()
        minuteur = QtCore.QTimer(zone)
        minuteur.timeout.connect(vigie.battre)
        minuteur.start(2000)
        zone._vigie, zone._vigie_timer = vigie, minuteur
    except Exception:
        pass
    return app.exec()


def _maj_silencieuse(zone) -> None:
    from pipit.fenetre import FenetreReglages
    if zone.fenetre is None:
        zone.fenetre = FenetreReglages(zone)
    zone.fenetre.verifier_maj(manuel=False)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except BaseException as _exc:          # noqa: BLE001 — filet volontaire
        _rapport_crash(_exc)
        sys.exit(1)
