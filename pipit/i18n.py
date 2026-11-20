"""Textes de Pipit en français et en anglais, langue détectée automatiquement.

Règles (les mêmes que MountMonitor) :
* chaque clé existe dans les deux langues — un test l'exige ;
* les champs de format ({n}, {nom}…) sont les mêmes d'une langue à l'autre,
  sinon le texte lèverait une erreur à l'exécution, chez l'utilisateur ;
* une clé manquante retombe sur l'anglais, puis sur la clé elle-même :
  un texte non traduit est un défaut cosmétique, un bouton vide est une panne.

"""
from __future__ import annotations

import os
import sys

LANGUES = ("fr", "en")
_langue = None


def detecter() -> str:
    """Langue d'AFFICHAGE du système (pas celle des formats de date).

    Windows : GetUserDefaultUILanguage (la locale de format peut être
    britannique chez un francophone, et inversement). macOS : la liste
    AppleLanguages des préférences globales, lue sans lancer de commande.
    Linux : variables d'environnement.
    """
    for var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        val = os.environ.get(var, "")
        if val and val not in ("C", "POSIX") and not val.startswith("C."):
            return "fr" if val.lower().startswith("fr") else "en"
    if sys.platform == "win32":
        try:
            import ctypes
            langid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            return "fr" if (langid & 0x3FF) == 0x0C else "en"
        except Exception:
            pass
    if sys.platform == "darwin":
        try:
            import plistlib
            from pathlib import Path
            chemin = Path.home() / "Library" / "Preferences" / ".GlobalPreferences.plist"
            with open(chemin, "rb") as f:
                langues = plistlib.load(f).get("AppleLanguages") or []
            if langues:
                return "fr" if str(langues[0]).lower().startswith("fr") else "en"
        except Exception:
            pass
    return "en"


def definir_langue(code: str | None) -> str:
    """Fixe la langue ('fr', 'en', ou None/'auto' pour la détection)."""
    global _langue
    _langue = code if code in LANGUES else detecter()
    return _langue


def langue() -> str:
    return _langue or definir_langue(None)


def tr(cle: str, **champs) -> str:
    """Texte dans la langue choisie."""
    textes = TEXTES.get(cle)
    if not textes:
        return cle
    modele = textes.get(langue()) or textes.get("en") or cle
    try:
        return modele.format(**champs) if champs else modele
    except (KeyError, IndexError, ValueError):
        return modele


def pluriel(n: int, cle_un: str, cle_plusieurs: str, **champs) -> str:
    return tr(cle_un if n == 1 else cle_plusieurs, n=n, **champs)




def _t(fr: str, en: str) -> dict[str, str]:
    return {"fr": fr, "en": en}


TEXTES: dict[str, dict[str, str]] = {
    # ---- général
    "cli.description": _t("Retirer une clé ou un disque USB sans risque, depuis l'icône près de l'horloge.",
                          "Safely remove USB drives and memory cards from the icon next to the clock."),
    "demarrage.echec": _t("Pipit n'a pas pu démarrer :\n{erreur}\n\nDétails enregistrés dans :\n{chemin}",
                          "Pipit could not start:\n{erreur}\n\nDetails saved in:\n{chemin}"),
    "demarrage.sans_zone": _t("La zone de notification (près de l'horloge) n'est pas disponible : Pipit ne peut "
                              "pas s'y installer.",
                              "The notification area (next to the clock) is not available: Pipit cannot "
                              "place its icon there."),
    "demarrage.question": _t("Lancer Pipit à chaque démarrage de Windows ?",
                             "Start Pipit every time Windows starts?"),
    "demarrage.question.texte": _t("Pipit vit dans la zone près de l'horloge. Lancé avec Windows, il est "
                                   "toujours là quand vous branchez une clé. Modifiable dans les réglages.",
                                   "Pipit lives next to the clock. Started with Windows, it is always there "
                                   "when you plug in a drive. You can change this in the settings."),
    "dlg.oui": _t("Oui", "Yes"),
    "dlg.non": _t("Non", "No"),
    "dlg.annuler": _t("Annuler", "Cancel"),
    "accord.titre": _t("Envoyer automatiquement les rapports d'incident ?", "Send incident reports automatically?"),
    "accord.texte": _t("Si Pipit plante ou se fige, un rapport technique (version, système, trace de l'erreur) "
                       "peut partir tout seul pour aider à corriger le défaut. Il ne contient ni vos fichiers ni "
                       "la liste de vos périphériques. Modifiable à tout moment dans les réglages.",
                       "If Pipit crashes or freezes, a technical report (version, system, error trace) can be "
                       "sent automatically to help fix the defect. It contains neither your files nor the list "
                       "of your devices. You can change this at any time in the settings."),
    "a_propos.texte": _t("<b>Pipit {version}</b><br>Retirer une clé USB, un disque externe ou une carte mémoire "
                         "sans risque, en un clic ou d'un raccourci clavier, et savoir quel programme "
                         "l'empêche.<br><br>Logiciel libre — ARP273-ROSE",
                         "<b>Pipit {version}</b><br>Safely remove a USB stick, an external drive or a memory "
                         "card in one click or with a keyboard shortcut, and find out which program is in the "
                         "way.<br><br>Free software — ARP273-ROSE"),
    # ---- menus communs
    "menu.quitter": _t("Quitter Pipit", "Quit Pipit"),
    "menu.langue": _t("Langue", "Language"),
    "menu.langue.auto": _t("Automatique (langue du système)", "Automatic (system language)"),
    "menu.langue.fr": _t("Français", "Français"),
    "menu.langue.en": _t("English", "English"),
    "menu.manuel": _t("Manuel (PDF)", "User guide (PDF)"),
    "menu.maj": _t("Rechercher une mise à jour", "Check for updates"),
    "menu.signaler": _t("Signaler un problème…", "Report a problem…"),
    "menu.rapports_auto": _t("Envoyer automatiquement les rapports d'incident",
                             "Send incident reports automatically"),
    "menu.a_propos": _t("À propos", "About"),
    # ---- icône et menu
    "zone.infobulle.aucun": _t("Pipit — aucun périphérique à retirer", "Pipit — nothing to remove"),
    "zone.infobulle.un": _t("Pipit — 1 périphérique à retirer", "Pipit — 1 device to remove"),
    "zone.infobulle.plusieurs": _t("Pipit — {n} périphériques à retirer", "Pipit — {n} devices to remove"),
    "zone.titre": _t("Retirer en toute sécurité :", "Safely remove:"),
    "zone.aucun": _t("Aucun périphérique à retirer", "No device to remove"),
    "zone.vide": _t("(vide)", "(empty)"),
    "zone.tout": _t("Tout éjecter", "Eject all"),
    "zone.ouvrir": _t("Ouvrir dans l'Explorateur", "Open in File Explorer"),
    "zone.reglages": _t("Réglages…", "Settings…"),
    # ---- éjection
    "ejecte.titre": _t("Vous pouvez débrancher", "Safe to remove"),
    "ejecte.texte": _t("« {nom} » peut être retiré en toute sécurité.", "“{nom}” can now be safely removed."),
    "lecteur.question": _t("« {nom} » est un lecteur à plusieurs fentes ({lettres}). Windows ne sait éjecter que "
                           "le lecteur entier : toutes ses cartes seront retirées.",
                           "“{nom}” is a multi-slot reader ({lettres}). Windows can only eject the whole "
                           "reader: all its cards will be removed."),
    "lecteur.ne_plus_demander": _t("Ne plus demander", "Don't ask again"),
    "lecteur.ejecter": _t("Éjecter le lecteur", "Eject the reader"),
    "refus.titre": _t("Windows refuse de retirer « {nom} » pour l'instant.",
                      "Windows refuses to remove “{nom}” for now."),
    "veto.ouvert": _t("Un programme utilise encore un fichier ou un dossier de ce périphérique.",
                      "A program is still using a file or folder on this device."),
    "veto.droits": _t("Windows demande des droits d'administrateur pour ce périphérique.",
                      "Windows requires administrator rights for this device."),
    "veto.service": _t("Un service de Windows le retient : {detail}", "A Windows service is holding it: {detail}"),
    "veto.appli": _t("Une application le retient : {detail}", "An application is holding it: {detail}"),
    "veto.erreur": _t("Erreur du système : {detail}", "System error: {detail}"),
    "refus.programme": _t("Programme en cause : {programme} (n° {pid}). Enregistrez votre travail, puis fermez-le.",
                          "Program in the way: {programme} (no. {pid}). Save your work, then close it."),
    "refus.explorateur": _t("C'est l'Explorateur de fichiers : fermez la fenêtre ouverte sur ce lecteur (ou "
                            "l'aperçu d'un fichier), puis réessayez.",
                            "It is File Explorer: close the window open on this drive (or a file preview), "
                            "then try again."),
    "refus.patienter": _t("{programme} (antivirus ou indexation) examine le périphérique : il le lâche en "
                          "général au bout de quelques secondes. Réessayez.",
                          "{programme} (antivirus or indexing) is scanning the device: it usually lets go "
                          "after a few seconds. Try again."),
    "refus.inconnu": _t("Windows n'a pas dit quel programme. Fermez les fenêtres et documents ouverts depuis "
                        "ce périphérique, puis réessayez.",
                        "Windows did not say which program. Close the windows and documents opened from this "
                        "device, then try again."),
    "refus.fermer": _t("Fermer {programme}", "Close {programme}"),
    "refus.reessayer": _t("Réessayer", "Try again"),
    # ---- fenêtre des réglages
    "fen.titre": _t("Pipit {version} — réglages", "Pipit {version} — settings"),
    "fen.entete": _t("Pipit", "Pipit"),
    "fen.sous_titre": _t("Cliquez sur l'icône près de l'horloge pour retirer une clé, un disque ou une carte. "
                         "Fermer cette fenêtre ne quitte pas Pipit.",
                         "Click the icon next to the clock to remove a drive or a card. Closing this window "
                         "does not quit Pipit."),
    "fen.peripheriques": _t("Périphériques branchés", "Connected devices"),
    "fen.peripheriques.aide": _t("Double-cliquez sur un nom pour le changer. Un périphérique masqué n'apparaît "
                                 "plus dans le menu ; Pipit s'en souvient même débranché.",
                                 "Double-click a name to change it. A hidden device no longer appears in the "
                                 "menu; Pipit remembers it even when unplugged."),
    "col.lettres": _t("Lecteur", "Drive"),
    "col.nom": _t("Nom affiché", "Displayed name"),
    "col.materiel": _t("Matériel", "Hardware"),
    "col.taille": _t("Taille", "Size"),
    "col.bus": _t("Branchement", "Connection"),
    "col.masquer": _t("Masquer", "Hide"),
    "fen.raccourcis": _t("Raccourcis clavier", "Keyboard shortcuts"),
    "fen.raccourci_menu": _t("Ouvrir le menu :", "Open the menu:"),
    "fen.raccourci_tout": _t("Tout éjecter :", "Eject all:"),
    "fen.raccourci_pris": _t("Déjà pris par un autre programme : {raccourcis}. Choisissez-en un autre.",
                             "Already taken by another program: {raccourcis}. Pick another one."),
    "fen.aucun": _t("(aucun)", "(none)"),
    "fen.options": _t("Options", "Options"),
    "fen.fermer": _t("Fermer", "Close"),
    "opt.notifier": _t("Prévenir quand on peut débrancher", "Notify when it is safe to unplug"),
    "opt.lecteur": _t("Demander avant d'éjecter un lecteur multicarte", "Ask before ejecting a multi-card reader"),
    "opt.internes": _t("Montrer aussi les disques internes branchés à chaud", "Also show hot-plug internal disks"),
    "opt.internes.aide": _t("Windows présente souvent les disques SATA comme « amovibles ». Ils sont cachés par "
                            "défaut pour éviter d'éjecter un disque interne par erreur.",
                            "Windows often presents SATA disks as “removable”. They are hidden by default so "
                            "that an internal disk is not ejected by mistake."),
    "opt.demarrage": _t("Lancer Pipit au démarrage de Windows", "Start Pipit with Windows"),
    # ---- mises à jour
    "maj.titre": _t("Mise à jour de Pipit", "Pipit update"),
    "maj.a_jour": _t("Pipit {version} est à jour.", "Pipit {version} is up to date."),
    "maj.dispo": _t("La version {nouvelle} est disponible (vous avez la {version}).",
                    "Version {nouvelle} is available (you have {version})."),
    "maj.installer": _t("Installer maintenant", "Install now"),
    "maj.page": _t("Ouvrir la page", "Open the page"),
    "maj.plus_tard": _t("Plus tard", "Later"),
    "maj.telechargement": _t("Téléchargement de la mise à jour…", "Downloading the update…"),
    "maj.echec": _t("La mise à jour a échoué : {erreur}", "The update failed: {erreur}"),
    "maj.redemarre": _t("Mise à jour installée : Pipit va redémarrer.", "Update installed: Pipit will restart."),
    # ---- signalement
    "signal.titre": _t("Signaler un problème", "Report a problem"),
    "signal.invite": _t("Décrivez ce qui s'est passé :", "Describe what happened:"),
    "signal.exemple": _t("Par exemple : ma clé n'apparaît pas dans le menu alors qu'elle est branchée.",
                         "For example: my USB stick does not appear in the menu although it is plugged in."),
    "signal.envoyer": _t("Envoyer", "Send"),
    "signal.merci": _t("Merci", "Thank you"),
    "signal.parti": _t("Merci, le signalement est parti.", "Thank you, the report was sent."),
    "signal.local": _t("Pas de réseau : le signalement a été enregistré ici :\n{chemin}",
                       "No network: the report was saved here:\n{chemin}"),
}
