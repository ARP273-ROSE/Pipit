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
    # ---- 0.2.0 : types de périphériques
    "type.auto": _t("Automatique ({type})", "Automatic ({type})"),
    "type.cle": _t("Clé USB", "USB stick"),
    "type.carte": _t("Carte mémoire", "Memory card"),
    "type.ssd": _t("SSD externe", "External SSD"),
    "type.hdd": _t("Disque dur externe", "External hard drive"),
    "type.interne": _t("Disque interne", "Internal disk"),
    "type.optique": _t("Lecteur CD/DVD", "CD/DVD drive"),
    "type.telephone": _t("Téléphone", "Phone"),
    "type.tablette": _t("Tablette", "Tablet"),
    "type.photo": _t("Appareil photo", "Camera"),
    "type.autre": _t("Autre", "Other"),
    "col.icone": _t("Icône", "Icon"),
    "col.type": _t("Type", "Type"),
    "icone.aide": _t("Changer l'icône de ce périphérique", "Change this device's icon"),
    "icone.choisir": _t("Choisir une image…", "Choose an image…"),
    "icone.defaut": _t("Icône du type", "Icon of the type"),
    "icone.filtre": _t("Images", "Images"),
    "icone.illisible": _t("Cette image n'a pas pu être lue.", "This image could not be read."),
    # ---- menus
    "zone.plus": _t("Plus d'options…", "More options…"),
    "zone.forcer": _t("Forcer l'éjection", "Force ejection"),
    "zone.coupables": _t("Qui utilise ce périphérique ?", "Who is using this device?"),
    "zone.remonter_titre": _t("Éjectés, encore branchés :", "Ejected, still plugged in:"),
    "zone.remonter": _t("Remonter « {nom} »", "Bring back “{nom}”"),
    # ---- refus, forçage, coupables
    "refus.autres": _t("… et {n} autre(s)", "… and {n} more"),
    "refus.chercher_partout": _t("Chercher partout…", "Search everywhere…"),
    "refus.forcer": _t("Forcer…", "Force…"),
    "forcer.question": _t("Forcer l'éjection de « {nom} » ?", "Force the ejection of “{nom}”?"),
    "forcer.texte": _t("Les caches sont d'abord vidés sur le disque, puis le volume est démonté même si des "
                       "fichiers sont encore ouverts : un document NON ENREGISTRÉ sur ce périphérique sera "
                       "perdu, et le programme qui l'avait ouvert peut afficher une erreur. Demande les droits "
                       "d'administrateur.",
                       "Caches are first written to the disk, then the volume is unmounted even if files are "
                       "still open: an UNSAVED document on this device will be lost, and the program that had "
                       "it open may show an error. Requires administrator rights."),
    "forcer.oui": _t("Forcer l'éjection", "Force ejection"),
    "forcer.echec": _t("L'éjection forcée a échoué ({detail}).", "The forced ejection failed ({detail})."),
    "remonte.titre": _t("Périphérique revenu", "Device is back"),
    "remonte.texte": _t("« {nom} » est de nouveau utilisable.", "“{nom}” can be used again."),
    "remonte.echec": _t("Windows n'a pas voulu remonter ce périphérique : débranchez-le puis rebranchez-le.",
                        "Windows would not bring this device back: unplug it and plug it in again."),
    "admin.uac_refuse": _t("Il faut accepter la demande de Windows (droits d'administrateur) pour ce geste.",
                           "You need to accept the Windows prompt (administrator rights) for this."),
    "coupables.titre": _t("Programmes qui utilisent « {nom} »", "Programs using “{nom}”"),
    "coupables.inconnu": _t("La recherche n'a pas abouti (un programme ne répond pas). Si cela se répète, "
                            "quittez puis relancez Pipit.",
                            "The search did not complete (a program is not responding). If it happens again, "
                            "quit and restart Pipit."),
    "coupables.aucun": _t("Aucun de vos programmes n'a de fichier ouvert dessus. « Chercher partout » regarde "
                          "aussi les programmes de Windows et l'antivirus (droits d'administrateur).",
                          "None of your programs has a file open on it. “Search everywhere” also looks at "
                          "Windows programs and the antivirus (administrator rights)."),
    "coupables.aucun_partout": _t("Aucun programme n'a de fichier ouvert dessus.",
                                  "No program has a file open on it."),
    "coupables.ejecter": _t("Éjecter", "Eject"),
    # ---- fin de session
    "oubli.titre": _t("Des périphériques sont encore branchés :", "Some devices are still plugged in:"),
    "oubli.ejecter": _t("Tout éjecter", "Eject all"),
    "oubli.continuer": _t("Continuer sans éjecter", "Continue without ejecting"),
    # ---- réglages
    "fen.assistant": _t("Assistant administrateur", "Administrator helper"),
    "opt.appareils": _t("Montrer téléphones, tablettes et appareils photo", "Show phones, tablets and cameras"),
    "opt.compteur": _t("Nombre de périphériques sur l'icône", "Number of devices on the icon"),
    "opt.rappel": _t("Rappeler les périphériques oubliés à la fermeture de session",
                     "Remind about forgotten devices when signing out"),
    "opt.rappel.aide": _t("À l'arrêt ou à la fermeture de session, Pipit propose de tout éjecter s'il reste "
                          "quelque chose de branché.",
                          "On shutdown or sign-out, Pipit offers to eject everything if something is still "
                          "plugged in."),
    "opt.theme": _t("Thème", "Theme"),
    "theme.sombre": _t("Sombre", "Dark"),
    "theme.clair": _t("Clair", "Light"),
    # ---- 0.3.0 : lecteurs CD/DVD et images
    "type.virtuel": _t("Lecteur virtuel (ISO, VHD)", "Virtual drive (ISO, VHD)"),
    "geste.tiroir": _t("ouvrir le tiroir", "open the tray"),
    "geste.demonter": _t("démonter l'image", "unmount the image"),
    "zone.fermer_tiroir": _t("Fermer le tiroir", "Close the tray"),
    "demonte.titre": _t("Image démontée", "Image unmounted"),
    "demonte.texte": _t("« {nom} » n'est plus monté.", "“{nom}” is no longer mounted."),
    "echec.tiroir": _t("Le tiroir de « {nom} » ne s'est pas ouvert (disque en cours de lecture ou de gravure ?).",
                       "The tray of “{nom}” did not open (disc being read or burned?)."),
    "echec.demonter": _t("« {nom} » n'a pas pu être démonté. Fermez les fichiers ouverts depuis ce lecteur, puis "
                         "réessayez.",
                         "“{nom}” could not be unmounted. Close the files opened from this drive, then try again."),
    "opt.optiques": _t("Montrer les lecteurs CD/DVD et les images ISO/VHD", "Show CD/DVD drives and ISO/VHD images"),
    "refus.montrer": _t("Montrer {programme}", "Show {programme}"),
    "assistant.uac": _t("Remonter, forcer l'éjection et « Chercher partout » demandent les droits "
                        "d'administrateur : Windows affiche sa fenêtre de confirmation à chaque fois. C'est voulu : "
                        "aucun programme ne peut s'en servir en cachette.",
                        "Bringing back, forcing ejection and “Search everywhere” require administrator rights: "
                        "Windows shows its confirmation prompt every time. This is deliberate: no program can use "
                        "them behind your back."),
    "assistant.ancienne": _t("La tâche « Pipit\\Assistant » de la version 0.2.0 est encore installée. Elle présente "
                             "un risque de sécurité : retirez-la (une confirmation de Windows).",
                             "The “Pipit\\Assistant” task from version 0.2.0 is still installed. It is a security "
                             "risk: remove it (one Windows confirmation)."),
    "assistant.retirer_ancienne": _t("Retirer l'ancienne tâche", "Remove the old task"),
    "dlg.plus_tard": _t("Plus tard", "Later"),
}
