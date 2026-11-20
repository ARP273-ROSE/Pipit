"""Faux périphériques : essais hors Windows et captures du manuel (PIPIT_DEMO=1).

Ce sont des noms de matériel génériques, rien qui vienne d'un vrai poste.
"""
from __future__ import annotations

import os

from .modele import Disque

_retires: set[str] = set()
_en_attente: dict[str, str] = {}

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
    Disque(6, "Samsung Portable SSD T7", "USB", 1_000_204_886_016, ["H"], ["MONTAGE"],
           "SCSI\\DISK&VEN_SAMSUNG&PROD_PORTABLE_SSD_T7\\9", "USB\\VID_04E8&PID_4001\\CC03",
           "USB\\ROOT_HUB30\\5", False, ssd=True),
    Disque(-1, "Apple iPad", "USB", 0, [], [], "SWD\\WPDBUSENUM\\IPAD", "USB\\VID_05AC&PID_12AB\\DD04",
           "USB\\ROOT_HUB30\\5", appareil="telephone"),
    Disque(1000, "HL-DT-ST DVDRAM GH24NSD1", "SATA", 0, ["T"], [""], "SCSI\\CDROM&VEN_HL-DT-ST\\10",
           appareil="optique"),
    Disque(1001, "Microsoft Virtual DVD-ROM", "Fichier", 4_700_000_000, ["V"], ["WIN11_FR"],
           "SCSI\\CDROM&VEN_MSFT&PROD_VIRTUAL_DVD-ROM\\11", appareil="optique"),
]
_tiroirs: dict[str, bool] = {}


def lister() -> list[Disque]:
    if os.environ.get("PIPIT_DEMO_VIDE") == "1":
        return [d for d in _DISQUES if d.bus in ("NVMe", "SATA") and not d.appareil]
    return [d for d in _DISQUES if d.id_ejectable not in _retires and d.id_disque not in _retires]


def ejecter(id_ejectable: str) -> tuple[int, str]:
    if os.environ.get("PIPIT_DEMO_REFUS") == "1":
        return 5, "STORAGE\\VOLUME\\{demo}"
    _retires.add(id_ejectable)
    _en_attente[id_ejectable] = next((d.nom for d in _DISQUES if d.id_ejectable == id_ejectable), "?")
    return 0, ""


def ouvrir_tiroir(lettre: str) -> bool:
    _tiroirs[lettre] = True
    return True


def fermer_tiroir(lettre: str) -> bool:
    _tiroirs[lettre] = False
    return True


def demonter_image(lettre: str) -> bool:
    for d in _DISQUES:
        if lettre in d.lettres and d.bus == "Fichier":
            _retires.add(d.id_disque)
            return True
    return False


def remettre() -> None:
    _retires.clear()
    _tiroirs.clear()
    _en_attente.clear()


def en_attente_de_retrait() -> list[tuple[str, str]]:
    return list(_en_attente.items())


def assistant(action: str, ident: str) -> dict:
    lettres = [l for d in _DISQUES if d.id_ejectable == ident for l in d.lettres]
    if action == "remonter":
        if ident not in _en_attente:
            return {"ok": False, "detail": "etat"}
        _retires.discard(ident)
        _en_attente.pop(ident, None)
        return {"ok": True, "methode": "demo"}
    if action == "forcer":
        _retires.add(ident)
        _en_attente[ident] = "?"
        return {"ok": True}
    return {"ok": True, "coupables": [{"pid": 4242, "programme": "WINWORD.EXE", "chemin_programme": "",
                                        "fichiers": [f"{(lettres or ['E'])[0]}:\\Rapport.docx"]}]}


def bloqueurs():
    from .bloqueurs import Bloqueur
    return [Bloqueur(4242, "WINWORD.EXE", "\\Device\\HarddiskVolume3\\Program Files\\Microsoft Office\\WINWORD.EXE")]
