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


def visible(p: Peripherique, internes_a_chaud: bool = False) -> bool:
    """Externe (USB, carte SD…), jamais le disque de Windows. Les disques SATA branchés
    à chaud passent pour « amovibles » aux yeux de Windows : cachés sauf demande."""
    if any(d.systeme for d in p.disques):
        return False
    return internes_a_chaud or p.bus in BUS_EXTERNES


def lister(masques: set[str] | None = None, internes_a_chaud: bool = False,
           avec_masques: bool = False) -> list[Peripherique]:
    masques = {m.upper() for m in (masques or set())}
    perifs = [p for p in regrouper(tous_les_disques()) if visible(p, internes_a_chaud)]
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


def ejecter(p: Peripherique, essais: int = 2) -> Resultat:
    """Éjecte ; en cas de refus, refait un essai (un antivirus qui scanne la clé la lâche
    souvent dans la seconde) puis cherche qui retient le périphérique."""
    debut = time.time()
    veto, nom = 0, ""
    for i in range(essais):
        veto, nom = _moteur().ejecter(p.id)
        if veto == 0:
            return Resultat(True)
        if veto == VETO_DEJA_RETIRE:
            return Resultat(True, veto)
        if i + 1 < essais:
            time.sleep(1.0)
    from . import bloqueurs
    return Resultat(False, veto, nom, bloqueurs.chercher(depuis=debut - 2, lettres=p.lettres))
