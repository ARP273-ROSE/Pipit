"""Faux périphériques : essais hors Windows et captures du manuel (PIPIT_DEMO=1).

Ce sont des noms de matériel génériques, rien qui vienne d'un vrai poste.
"""
from __future__ import annotations

import os

from .modele import Disque

_retires: set[str] = set()

_DISQUES = [
    Disque(0, "Samsung SSD 990 PRO 2TB", "NVMe", 2_000_398_934_016, ["C"], ["Windows"],
           "SCSI\\DISK&VEN_NVME\\1", "", "", False, True),
    Disque(1, "ST4000DM004-2CV104", "SATA", 4_000_787_030_016, ["D"], ["Données"],
           "SCSI\\DISK&VEN_ST4000\\2", "PCIIDE\\IDECHANNEL\\4&1&0", "PCI\\VEN_1022&DEV_43EB\\3", False),
    Disque(2, "SanDisk Extreme Pro USB Device", "USB", 1_000_204_886_016, ["E"], ["SAUVEGARDE"],
           "USBSTOR\\DISK&VEN_SANDISK\\4", "USB\\VID_0781&PID_558C\\AA01", "USB\\ROOT_HUB30\\5", True),
    Disque(3, "Generic STORAGE DEVICE (SD)", "USB", 63_864_569_856, ["F"], ["NIKON Z"],
           "USBSTOR\\DISK&VEN_GENERIC&PROD_SD\\6", "USB\\VID_05E3&PID_0749\\0000", "USB\\ROOT_HUB30\\5", True),
    Disque(4, "Generic STORAGE DEVICE (CF)", "USB", 0, [], [],
           "USBSTOR\\DISK&VEN_GENERIC&PROD_CF\\7", "USB\\VID_05E3&PID_0749\\0000", "USB\\ROOT_HUB30\\5", True),
    Disque(5, "Kingston DataTraveler 3.0", "USB", 31_037_849_600, ["G"], ["CLE"],
           "USBSTOR\\DISK&VEN_KINGSTON\\8", "USB\\VID_0951&PID_1666\\BB02", "USB\\ROOT_HUB30\\5", True),
]


def lister() -> list[Disque]:
    if os.environ.get("PIPIT_DEMO_VIDE") == "1":
        return [d for d in _DISQUES if d.bus in ("NVMe", "SATA")]
    return [d for d in _DISQUES if d.id_ejectable not in _retires]


def ejecter(id_ejectable: str) -> tuple[int, str]:
    if os.environ.get("PIPIT_DEMO_REFUS") == "1":
        return 5, "STORAGE\\VOLUME\\{demo}"
    _retires.add(id_ejectable)
    return 0, ""


def remettre() -> None:
    _retires.clear()


def bloqueurs():
    from .bloqueurs import Bloqueur
    return [Bloqueur(4242, "WINWORD.EXE", "\\Device\\HarddiskVolume3\\Program Files\\Microsoft Office\\WINWORD.EXE")]
