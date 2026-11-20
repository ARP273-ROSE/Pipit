"""Liste des périphériques à retirer et éjection, quel que soit le système.

Sous Windows : disques_windows.py. Ailleurs, ou avec PIPIT_DEMO=1 : demo.py
(essais, captures d'écran du manuel).
"""
from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass

from .modele import Disque, Peripherique, regrouper

BUS_EXTERNES = {"USB", "SD", "MMC", "1394"}

# PNP_VETO_TYPE : pourquoi Windows refuse
VETO_INCONNU, VETO_APPLI, VETO_SERVICE, VETO_FICHIER_OUVERT, VETO_PERIPH = 0, 3, 4, 5, 6
VETO_DROITS, VETO_DEJA_RETIRE = 12, 13


def demo() -> bool:
    return os.environ.get("PIPIT_DEMO") == "1" or sys.platform != "win32"


def _moteur():
    if demo():
        from . import demo as m
    else:
        from . import disques_windows as m
    return m


def tous_les_disques() -> list[Disque]:
    return _moteur().lister()


def visible(p: Peripherique, internes_a_chaud: bool = False, appareils: bool = True,
            optiques: bool = True) -> bool:
    """Externe (USB, carte SD…), jamais le disque de Windows. Les disques SATA branchés
    à chaud passent pour « amovibles » aux yeux de Windows : cachés sauf demande.
    Téléphones, tablettes, appareils photo : montrés sauf demande."""
    if any(d.systeme for d in p.disques):
        return False
    if p.type in ("optique", "virtuel"):
        return optiques and bool(p.lettres)
    if any(d.appareil for d in p.disques):
        return appareils
    return internes_a_chaud or p.bus in BUS_EXTERNES


def lister(masques: set[str] | None = None, internes_a_chaud: bool = False,
           avec_masques: bool = False, appareils: bool = True, optiques: bool = True) -> list[Peripherique]:
    masques = {m.upper() for m in (masques or set())}
    perifs = [p for p in regrouper(tous_les_disques()) if visible(p, internes_a_chaud, appareils, optiques)]
    if not avec_masques:
        perifs = [p for p in perifs if p.materiel not in masques]
    return perifs


@dataclass
class Resultat:
    ok: bool
    veto: int = 0
    detail: str = ""          # nom du service, du périphérique ou du programme fautif
    bloqueurs: list = None    # [Bloqueur] trouvés dans le journal de Windows

    def __post_init__(self):
        self.bloqueurs = self.bloqueurs or []


def _fichier_noms():
    from . import systeme
    return systeme.dossier_donnees() / "ejectes.json"


def memoriser(p: Peripherique) -> None:
    """Retient le nom d'un périphérique éjecté : une fois éjecté, Windows ne donne plus que
    le nom générique du pilote (« Dispositif de stockage de masse UAS »)."""
    import json
    try:
        noms = json.loads(_fichier_noms().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        noms = {}
    noms[p.id] = p.nom
    try:
        _fichier_noms().write_text(json.dumps(dict(list(noms.items())[-50:]), ensure_ascii=False),
                                   encoding="utf-8")
    except OSError:
        pass


def ejecter(p: Peripherique, essais: int = 2, chercher: bool = True) -> Resultat:
    """Éjecte ; en cas de refus, refait un essai (un antivirus qui scanne la clé la lâche
    souvent dans la seconde) puis cherche qui retient le périphérique. Un lecteur CD/DVD
    ouvre son tiroir ; une image ISO/VHD est démontée."""
    if p.geste == "tiroir":
        ok = _moteur().ouvrir_tiroir(p.lettres[0])
        return Resultat(ok, 0 if ok else -1, "" if ok else "tiroir")
    if p.geste == "demonter":
        ok = all(_moteur().demonter_image(l) for l in p.lettres)
        return Resultat(ok, 0 if ok else -1, "" if ok else "image")
    debut = time.time()
    veto, nom = 0, ""
    for i in range(essais):
        veto, nom = _moteur().ejecter(p.id)
        if veto == 0:
            memoriser(p)
            return Resultat(True)
        if veto == VETO_DEJA_RETIRE:
            return Resultat(True, veto)
        if i + 1 < essais:
            time.sleep(1.0)
    if not chercher:
        return Resultat(False, veto, nom)
    from . import bloqueurs, poignees
    trouves = bloqueurs.chercher(depuis=debut - 2, lettres=p.lettres,
                                 ids=[p.id] + [d.id_disque for d in p.disques])
    # le journal de Windows ne note pas tout : on regarde aussi les fichiers ouverts
    # par les programmes de l'utilisateur (sans droits d'administrateur)
    connus = {b.pid for b in trouves}
    for c in poignees.chercher(p.lettres) or []:
        if c.pid not in connus:
            trouves.append(bloqueurs.Bloqueur(c.pid, c.programme, c.chemin_programme, c.fichiers))
    return Resultat(False, veto, nom, trouves)


# ------------------------------------------------------------------ éjectés, encore branchés
def en_attente_de_retrait() -> list[tuple[str, str]]:
    """[(identifiant, nom)] : éjectés mais pas débranchés, donc remontables."""
    import json
    try:
        liste = _moteur().en_attente_de_retrait()
    except Exception:                                   # noqa: BLE001
        return []
    try:
        noms = json.loads(_fichier_noms().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        noms = {}
    return [(i, noms.get(i) or n) for i, n in liste]


def remonter(ident: str) -> dict:
    from . import assistant
    return assistant.demander("remonter", ident)


def forcer(p: Peripherique) -> dict:
    from . import assistant
    r = assistant.demander("forcer", p.id)
    if r.get("ok"):
        memoriser(p)
    return r


def coupables(p: Peripherique, partout: bool = False) -> list | None:
    """Programmes qui ont des fichiers ouverts sur le périphérique. Sans `partout`, seulement
    ceux de l'utilisateur (sans droits) ; avec, par l'assistant administrateur (tous)."""
    from . import poignees
    if not partout:
        return poignees.chercher(p.lettres)
    from . import assistant
    r = assistant.demander("coupables", p.id)
    if not r.get("ok"):
        return None
    return [poignees.Coupable(**c) for c in r.get("coupables", [])]


def changer_lettre(p: Peripherique, ancienne: str, nouvelle: str) -> dict:
    """Lettre fixe : Windows la retient ensuite pour ce volume (une fenêtre UAC, une fois)."""
    from . import assistant
    return assistant.demander("lettre", p.id, ancienne.upper() + nouvelle.upper())


def regler_courant(p: Peripherique, couper: bool) -> dict:
    """Couper le courant du port après éjection (registre système : une fenêtre UAC)."""
    from . import assistant
    return assistant.demander("courant", p.id, "1" if couper else "0")


def lettres_libres() -> list[str]:
    """D à Z, sans celles déjà prises (lecteurs présents ou réseau)."""
    prises: set[str] = set()
    if not demo():
        import ctypes
        masque = ctypes.windll.kernel32.GetLogicalDrives()
        prises = {chr(65 + i) for i in range(26) if masque & (1 << i)}
    else:
        prises = {l for d in tous_les_disques() for l in d.lettres} | {"C"}
    return [chr(c) for c in range(ord("D"), ord("Z") + 1) if chr(c) not in prises]


def lancer_programme(commande: str, lettre: str) -> bool:
    """Programme choisi pour ce périphérique, lancé à son arrivée, avec les droits de
    l'utilisateur (jamais élevé). Un .exe reçoit la racine du lecteur en argument."""
    import subprocess
    from pathlib import Path
    chemin = Path(commande)
    if not commande or not chemin.exists():
        return False
    racine = f"{lettre}:\\" if lettre else ""
    try:
        if chemin.suffix.lower() in (".exe", ".com"):
            subprocess.Popen([str(chemin)] + ([racine] if racine else []),
                             cwd=racine or None, close_fds=True)
        elif sys.platform == "win32":
            os.startfile(str(chemin))                # noqa: S606 — fichier choisi par l'utilisateur
        else:
            return False
    except OSError:
        return False
    return True


def fermer_tiroir(p: Peripherique) -> bool:
    return bool(p.lettres) and _moteur().fermer_tiroir(p.lettres[0])
