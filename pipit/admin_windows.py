"""Gestes qui demandent les droits d'administrateur, exécutés par l'assistant (assistant.py).

* Éjection forcée : vider les caches du volume, le verrouiller si possible, le démonter
  (les fichiers encore ouverts deviennent invalides), puis demander l'éjection.
* Remontage : un périphérique éjecté mais resté branché est « prêt pour le retrait »
  (problème 47) ; on demande à Windows de le redémarrer sans le débrancher.

Mesuré sur un vrai poste : sans droits d'administrateur, toutes les fonctions de remontage
répondent CR_ACCESS_DENIED (51).
"""
from __future__ import annotations

import ctypes
import time
from ctypes import wintypes

from . import disques_windows as dw

kernel32 = dw.kernel32
cfgmgr32 = dw.cfgmgr32

GENERIC_RW = 0x80000000 | 0x40000000
FSCTL_LOCK_VOLUME, FSCTL_DISMOUNT_VOLUME = 0x90018, 0x90020
IOCTL_STORAGE_MEDIA_REMOVAL = 0x2D4804
CM_LOCATE_DEVNODE_PHANTOM = 0x1
CM_REENUMERATE_SYNCHRONOUS, CM_REENUMERATE_RETRY_INSTALLATION = 0x1, 0x2
CM_SETUP_DEVNODE_READY = 0x0
CM_DISABLE_UI_NOT_OK = 0x4
DN_STARTED, DN_HAS_PROBLEM = 0x8, 0x400
CM_PROB_HELD_FOR_EJECT = 47

kernel32.FlushFileBuffers.argtypes = [wintypes.HANDLE]
cfgmgr32.CM_Get_DevNode_Status.argtypes = [ctypes.POINTER(wintypes.ULONG), ctypes.POINTER(wintypes.ULONG),
                                           wintypes.DWORD, wintypes.ULONG]
cfgmgr32.CM_Reenumerate_DevNode.argtypes = [wintypes.DWORD, wintypes.ULONG]
cfgmgr32.CM_Setup_DevNode.argtypes = [wintypes.DWORD, wintypes.ULONG]
cfgmgr32.CM_Disable_DevNode.argtypes = [wintypes.DWORD, wintypes.ULONG]
cfgmgr32.CM_Enable_DevNode.argtypes = [wintypes.DWORD, wintypes.ULONG]


# ------------------------------------------------------------------ éjection forcée
def _demonter(lettre: str):
    """(poignée verrouillée ou None, étape). La poignée reste ouverte jusqu'à l'éjection :
    sinon l'Explorateur, l'antivirus ou un sondage remonte le volume entre-temps."""
    h = kernel32.CreateFileW(f"\\\\.\\{lettre}:", GENERIC_RW, dw.FILE_SHARE_RW, None, dw.OPEN_EXISTING, 0, None)
    if h in (None, dw.INVALID_HANDLE):
        return None, "ouverture"
    kernel32.FlushFileBuffers(h)                # ce qui est en mémoire part sur le disque d'abord
    verrou = False
    for _ in range(3):
        if dw._ioctl(h, FSCTL_LOCK_VOLUME, taille_sortie=0) is not None:
            verrou = True
            break
        time.sleep(0.4)
    dw._ioctl(h, FSCTL_DISMOUNT_VOLUME, taille_sortie=0)
    if verrou:
        dw._ioctl(h, IOCTL_STORAGE_MEDIA_REMOVAL, b"\0", 0)
    return h, ("verrouille" if verrou else "demonte_de_force")


def forcer(id_ejectable: str, lettres: list[str]) -> dict:
    """Chaque essai reverrouille et redémonte les volumes, et les garde verrouillés pendant
    la demande d'éjection : l'Explorateur ou l'antivirus n'ont pas le temps de les remonter.
    Si nos propres poignées gênent, un essai sans elles suit aussitôt."""
    etapes, veto, nom = {}, 0, ""
    for _ in range(3):
        poignees = []
        for l in lettres:
            h, etape = _demonter(l)
            etapes[l] = etape
            if h is not None:
                poignees.append(h)
        try:
            veto, nom = dw.ejecter(id_ejectable)
        finally:
            for h in poignees:
                kernel32.CloseHandle(h)
        if veto in (0, 13):
            return {"ok": True, "etapes": etapes}
        veto, nom = dw.ejecter(id_ejectable)
        if veto in (0, 13):
            return {"ok": True, "etapes": etapes}
        time.sleep(1.0)
    return {"ok": False, "veto": veto, "detail": nom, "etapes": etapes}


# ------------------------------------------------------------------ remontage
def _localiser(ident: str) -> int | None:
    d = wintypes.DWORD()
    for drapeau in (0, CM_LOCATE_DEVNODE_PHANTOM):
        if cfgmgr32.CM_Locate_DevNodeW(ctypes.byref(d), ident, drapeau) == dw.CR_SUCCESS:
            return d.value
    return None


def etat(ident: str) -> tuple[bool, int]:
    """(présent et démarré, numéro de problème)."""
    dn = _localiser(ident)
    if dn is None:
        return False, -1
    st, pb = wintypes.ULONG(), wintypes.ULONG()
    if cfgmgr32.CM_Get_DevNode_Status(ctypes.byref(st), ctypes.byref(pb), dn, 0) != dw.CR_SUCCESS:
        return False, -1
    probleme = pb.value if st.value & DN_HAS_PROBLEM else 0
    return bool(st.value & DN_STARTED) and not probleme, probleme


def en_attente_de_retrait(ident: str) -> bool:
    """Éjecté mais encore branché : c'est là qu'un remontage a un sens."""
    return etat(ident)[1] == CM_PROB_HELD_FOR_EJECT


def remonter(ident: str) -> dict:
    dn = _localiser(ident)
    if dn is None:
        return {"ok": False, "detail": "absent"}
    parent = dw._parent(dn)
    essais = [
        ("setup_ready", lambda: cfgmgr32.CM_Setup_DevNode(dn, CM_SETUP_DEVNODE_READY)),
        ("reenum_dev", lambda: cfgmgr32.CM_Reenumerate_DevNode(
            dn, CM_REENUMERATE_RETRY_INSTALLATION | CM_REENUMERATE_SYNCHRONOUS)),
        ("reenum_parent", lambda: cfgmgr32.CM_Reenumerate_DevNode(
            parent, CM_REENUMERATE_SYNCHRONOUS) if parent is not None else -1),
        ("desactiver_activer", lambda: (cfgmgr32.CM_Disable_DevNode(dn, CM_DISABLE_UI_NOT_OK),
                                        time.sleep(1.0), cfgmgr32.CM_Enable_DevNode(dn, 0))[2]),
    ]
    journal = []
    for nom, appel in essais:
        try:
            cr = appel()
        except Exception as exc:                # noqa: BLE001
            cr = f"{type(exc).__name__}"
        for _ in range(10):
            time.sleep(0.5)
            if etat(ident)[0]:
                journal.append(f"{nom}:{cr}:ok")
                return {"ok": True, "methode": nom, "journal": journal}
        journal.append(f"{nom}:{cr}:{etat(ident)[1]}")
    return {"ok": False, "detail": "refus", "journal": journal}
