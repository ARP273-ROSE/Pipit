"""Port USB d'un périphérique : vitesse réelle, redémarrage du port, coupure du courant.

* Vitesse : le concentrateur (hub) dit à quelle vitesse le périphérique fonctionne et s'il
  saurait aller plus vite (IOCTL_USB_GET_NODE_CONNECTION_INFORMATION_EX et _EX_V2, comme
  USBView). Sans droits d'administrateur.
* Redémarrage du port (IOCTL_USB_HUB_CYCLE_PORT) : coupe puis rétablit le port ; un
  périphérique éjecté mais encore branché revient. Droits d'administrateur depuis Windows 8.
* Coupure du courant après éjection : valeur DisableOnSoftRemove = 1 (REG_DWORD) sous
  HKLM\\SYSTEM\\CurrentControlSet\\Control\\usbflags\\VVVVPPPPRRRR (article Microsoft 2401954,
  écrit pour Vista et 7 ; les ports USB 3 de Windows 10/11 peuvent l'ignorer).
"""
from __future__ import annotations

import re
import struct
import sys

VITESSES = {0: "1.5 Mbit/s", 1: "12 Mbit/s", 2: "480 Mbit/s", 3: "5 Gbit/s", 4: "10 Gbit/s"}
NORMES = {0: "USB 1.0", 1: "USB 1.1", 2: "USB 2.0", 3: "USB 3", 4: "USB 3 (10 Gbit/s)"}

IOCTL_USB_GET_NODE_CONNECTION_INFORMATION_EX = 0x220448
IOCTL_USB_GET_NODE_CONNECTION_INFORMATION_EX_V2 = 0x22045C
IOCTL_USB_HUB_CYCLE_PORT = 0x220444
GUID_HUB = "f18a0e88-c30c-11d0-8815-00a0c906bed8"
CM_DRP_HARDWAREID, CM_DRP_ADDRESS = 0x2, 0x1D
CLE_USBFLAGS = r"SYSTEM\CurrentControlSet\Control\usbflags"
_VPR = re.compile(r"VID_([0-9A-F]{4})&PID_([0-9A-F]{4})(?:&REV_([0-9A-F]{4}))?", re.I)


def lisible(niveau: int) -> str:
    """« USB 3 — 5 Gbit/s » ; vide si inconnu."""
    if niveau not in NORMES:
        return ""
    return f"{NORMES[niveau].split(' (')[0]} — {VITESSES[niveau]}"


def bride(actuel: int, possible: int) -> bool:
    """Un périphérique USB 3 branché sur un port (ou un câble) USB 2."""
    return 0 <= actuel < 3 <= possible


def cle_usbflags(id_materiel: str) -> str:
    """« USB\\VID_0781&PID_558C&REV_1000 » → « 0781558C1000 » (nom de la sous-clé usbflags)."""
    m = _VPR.search(id_materiel or "")
    if not m or not m.group(3):
        return ""
    return (m.group(1) + m.group(2) + m.group(3)).upper()


# ------------------------------------------------------------------ Windows
def _dw():
    from . import disques_windows
    return disques_windows


def _interface_hub(devinst: int) -> str:
    """Chemin de l'interface « concentrateur USB » d'un nœud, ou "" s'il n'en est pas un."""
    import ctypes
    from ctypes import wintypes
    dw = _dw()
    cfg = dw.cfgmgr32
    cfg.CM_Get_Device_Interface_List_SizeW.argtypes = [ctypes.POINTER(wintypes.ULONG), ctypes.c_void_p,
                                                       wintypes.LPCWSTR, wintypes.ULONG]
    cfg.CM_Get_Device_Interface_ListW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR, wintypes.LPWSTR,
                                                  wintypes.ULONG, wintypes.ULONG]
    ident = dw._id(devinst)
    if not ident:
        return ""
    guid = dw._guid(GUID_HUB)
    n = wintypes.ULONG(0)
    if cfg.CM_Get_Device_Interface_List_SizeW(ctypes.byref(n), ctypes.byref(guid), ident, 0) != dw.CR_SUCCESS \
            or n.value < 2:
        return ""
    tampon = ctypes.create_unicode_buffer(n.value)
    if cfg.CM_Get_Device_Interface_ListW(ctypes.byref(guid), ident, tampon, n.value, 0) != dw.CR_SUCCESS:
        return ""
    return tampon.value


def _hub_et_port(id_usb: str) -> tuple[str, int] | None:
    """Remonte depuis le nœud jusqu'au premier parent qui est un concentrateur."""
    import ctypes
    from ctypes import wintypes
    dw = _dw()
    d = wintypes.DWORD()
    trouve = False
    for drapeau in (0, 1):                          # 1 = même s'il n'est plus démarré
        if dw.cfgmgr32.CM_Locate_DevNodeW(ctypes.byref(d), id_usb, drapeau) == dw.CR_SUCCESS:
            trouve = True
            break
    if not trouve:
        return None
    n = d.value
    for _ in range(6):
        parent = dw._parent(n)
        if parent is None:
            return None
        chemin = _interface_hub(parent)
        if chemin:
            port = dw._propriete(n, CM_DRP_ADDRESS)
            return (chemin, port) if isinstance(port, int) and port > 0 else None
        n = parent
    return None


def _ouvrir_hub(chemin: str, ecriture: bool):
    dw = _dw()
    acces = 0x40000000 if ecriture else 0             # GENERIC_WRITE (nécessaire au redémarrage)
    h = dw.kernel32.CreateFileW(chemin, acces, dw.FILE_SHARE_RW, None, dw.OPEN_EXISTING, 0, None)
    return None if h in (None, dw.INVALID_HANDLE) else h


_cache: dict[str, tuple[int, int]] = {}


def vitesse(id_usb: str) -> tuple[int, int]:
    """(vitesse actuelle, meilleure vitesse possible) : 0 à 4, -1 si inconnue. La vitesse ne
    change pas tant que le périphérique reste branché : lue une fois par branchement (l'identifiant
    d'instance change au rebranchement sur un autre port ; sur le même, la valeur reste juste)."""
    if sys.platform != "win32" or not id_usb.upper().startswith("USB\\"):
        return -1, -1
    if id_usb not in _cache:
        _cache[id_usb] = _vitesse(id_usb)
    return _cache[id_usb]


def oublier(ids_presents: set[str]) -> None:
    """Retire du cache les périphériques débranchés (relecture au prochain branchement)."""
    for i in list(_cache):
        if i not in ids_presents:
            del _cache[i]


def _vitesse(id_usb: str) -> tuple[int, int]:
    try:
        hp = _hub_et_port(id_usb)
        if hp is None:
            return -1, -1
        chemin, port = hp
        dw = _dw()
        h = _ouvrir_hub(chemin, False)
        if h is None:
            return -1, -1
        try:
            r = dw._ioctl(h, IOCTL_USB_GET_NODE_CONNECTION_INFORMATION_EX,
                          struct.pack("<I", port) + bytes(508), 512)
            if not r or len(r) < 24:
                return -1, -1
            actuel = r[23]
            bcd = struct.unpack_from("<H", r, 6)[0]
            possible = 3 if bcd >= 0x300 else actuel
            v2 = dw._ioctl(h, IOCTL_USB_GET_NODE_CONNECTION_INFORMATION_EX_V2,
                           struct.pack("<IIII", port, 16, 0x7, 0), 16)
            if v2 and len(v2) >= 16:
                # bit 0 : fonctionne en SuperSpeed ; 1 : en est capable ; 2 et 3 : idem en SuperSpeed+.
                # Le champ Speed de _EX dit « High » pour un périphérique SuperSpeed : seul _V2 tranche.
                drapeaux = struct.unpack_from("<I", v2, 12)[0]
                if drapeaux & 0x1:
                    actuel = max(actuel, 3)
                if drapeaux & 0x4:
                    actuel = 4
                if drapeaux & 0x8:
                    possible = 4
                elif drapeaux & 0x2:
                    possible = max(possible, 3)
            return (actuel if actuel in NORMES else -1), max(possible, actuel)
        finally:
            dw.kernel32.CloseHandle(h)
    except Exception:                                    # noqa: BLE001 — information de confort
        return -1, -1


def redemarrer_port(id_usb: str) -> int:
    """IOCTL_USB_HUB_CYCLE_PORT (administrateur). 0 = accepté, sinon code d'erreur."""
    import ctypes
    hp = _hub_et_port(id_usb)
    if hp is None:
        return -1
    chemin, port = hp
    dw = _dw()
    h = _ouvrir_hub(chemin, True)
    if h is None:
        return ctypes.get_last_error() or -2
    try:
        r = dw._ioctl(h, IOCTL_USB_HUB_CYCLE_PORT, struct.pack("<II", port, 0), 8)
        return 0 if r is not None else (ctypes.get_last_error() or -3)
    finally:
        dw.kernel32.CloseHandle(h)


def _id_materiel(id_usb: str) -> str:
    import ctypes
    from ctypes import wintypes
    dw = _dw()
    d = wintypes.DWORD()
    if dw.cfgmgr32.CM_Locate_DevNodeW(ctypes.byref(d), id_usb, 1) != dw.CR_SUCCESS:
        return ""
    v = dw._propriete(d.value, CM_DRP_HARDWAREID)
    return v if isinstance(v, str) else ""


def courant_coupe(id_usb: str) -> bool | None:
    """La coupure est-elle réglée pour ce matériel ? None = on ne sait pas."""
    if sys.platform != "win32":
        return None
    cle = cle_usbflags(_id_materiel(id_usb))
    if not cle:
        return None
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, CLE_USBFLAGS + "\\" + cle) as k:
            return winreg.QueryValueEx(k, "DisableOnSoftRemove")[0] == 1
    except OSError:
        return False


def regler_courant(id_usb: str, couper: bool) -> dict:
    """Écrit (ou retire) DisableOnSoftRemove pour ce seul matériel (administrateur)."""
    import winreg
    cle = cle_usbflags(_id_materiel(id_usb))
    if not cle:
        return {"ok": False, "detail": "materiel"}
    chemin = CLE_USBFLAGS + "\\" + cle
    try:
        if couper:
            with winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, chemin, 0, winreg.KEY_SET_VALUE) as k:
                winreg.SetValueEx(k, "DisableOnSoftRemove", 0, winreg.REG_DWORD, 1)
        else:
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, chemin, 0, winreg.KEY_SET_VALUE) as k:
                    winreg.DeleteValue(k, "DisableOnSoftRemove")
            except FileNotFoundError:
                pass
    except OSError as exc:
        return {"ok": False, "detail": str(exc)}
    return {"ok": True, "cle": cle}
