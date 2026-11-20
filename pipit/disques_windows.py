"""Disques amovibles sous Windows, par les API du système (ctypes), sans droits d'administrateur.

Chemin suivi, le même que l'icône « Retirer le périphérique » de Windows :

1. les disques présents (interface GUID_DEVINTERFACE_DISK, SetupAPI) ;
2. pour chacun, son numéro de disque, son bus (USB, SD…), sa taille ;
3. les lettres de lecteur rattachées par le numéro de disque ;
4. en remontant l'arbre des périphériques (cfgmgr32), le premier ancêtre
   « amovible » : c'est LUI que l'on éjecte (le boîtier USB, pas le disque) ;
5. l'éjection par CM_Request_Device_EjectW : Windows prévient les programmes,
   vide les caches, démonte les volumes ; s'il refuse, il dit pourquoi (veto).

Ouvrir un disque avec un accès nul (0) suffit pour ces IOCTL : pas d'UAC.
"""
from __future__ import annotations

import ctypes
import string
import struct
from ctypes import wintypes

from .modele import Disque

setupapi = ctypes.WinDLL("setupapi", use_last_error=True)
cfgmgr32 = ctypes.WinDLL("cfgmgr32")
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

ULONG_PTR = ctypes.c_size_t
INVALID_HANDLE = ctypes.c_void_p(-1).value

DIGCF_PRESENT, DIGCF_DEVICEINTERFACE = 0x2, 0x10
IOCTL_STORAGE_GET_DEVICE_NUMBER = 0x2D1080
IOCTL_STORAGE_QUERY_PROPERTY = 0x2D1400
IOCTL_DISK_GET_DRIVE_GEOMETRY_EX = 0x700A0
FILE_SHARE_RW = 0x1 | 0x2
OPEN_EXISTING = 3
FILE_DEVICE_DISK = 7
CM_DRP_DEVICEDESC, CM_DRP_FRIENDLYNAME, CM_DRP_CAPABILITIES = 0x1, 0xD, 0x10
CM_DEVCAP_REMOVABLE = 0x4
CR_SUCCESS, CR_REMOVE_VETOED = 0, 0x17
DRIVE_REMOVABLE, DRIVE_FIXED = 2, 3

# STORAGE_BUS_TYPE
BUS = {1: "SCSI", 2: "ATAPI", 3: "ATA", 4: "1394", 6: "Fibre", 7: "USB", 8: "RAID",
       10: "SAS", 11: "SATA", 12: "SD", 13: "MMC", 17: "NVMe", 15: "Fichier"}


class GUID(ctypes.Structure):
    _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]


def _guid(texte: str) -> GUID:
    t = texte.strip("{}").replace("-", "")
    g = GUID(int(t[0:8], 16), int(t[8:12], 16), int(t[12:16], 16))
    for i in range(8):
        g.Data4[i] = int(t[16 + 2 * i:18 + 2 * i], 16)
    return g


GUID_DEVINTERFACE_DISK = _guid("53f56307-b6bf-11d0-94f2-00a0c91efb8b")


class SP_DEVICE_INTERFACE_DATA(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("InterfaceClassGuid", GUID),
                ("Flags", wintypes.DWORD), ("Reserved", ULONG_PTR)]


class SP_DEVINFO_DATA(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("ClassGuid", GUID),
                ("DevInst", wintypes.DWORD), ("Reserved", ULONG_PTR)]


setupapi.SetupDiGetClassDevsW.restype = wintypes.HANDLE
setupapi.SetupDiGetClassDevsW.argtypes = [ctypes.POINTER(GUID), wintypes.LPCWSTR, wintypes.HWND, wintypes.DWORD]
setupapi.SetupDiEnumDeviceInterfaces.restype = wintypes.BOOL
setupapi.SetupDiEnumDeviceInterfaces.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.POINTER(GUID),
                                                 wintypes.DWORD, ctypes.POINTER(SP_DEVICE_INTERFACE_DATA)]
setupapi.SetupDiGetDeviceInterfaceDetailW.restype = wintypes.BOOL
setupapi.SetupDiGetDeviceInterfaceDetailW.argtypes = [
    wintypes.HANDLE, ctypes.POINTER(SP_DEVICE_INTERFACE_DATA), ctypes.c_void_p, wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(SP_DEVINFO_DATA)]
setupapi.SetupDiDestroyDeviceInfoList.argtypes = [wintypes.HANDLE]

kernel32.CreateFileW.restype = wintypes.HANDLE
kernel32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                                 wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
kernel32.DeviceIoControl.restype = wintypes.BOOL
kernel32.DeviceIoControl.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD,
                                     ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
                                     ctypes.c_void_p]
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.GetLogicalDrives.restype = wintypes.DWORD
kernel32.GetDriveTypeW.argtypes = [wintypes.LPCWSTR]
kernel32.GetVolumeInformationW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD,
                                           ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                                           wintypes.LPWSTR, wintypes.DWORD]
kernel32.GetSystemWindowsDirectoryW.argtypes = [wintypes.LPWSTR, wintypes.UINT]
kernel32.SetErrorMode.argtypes = [wintypes.UINT]
kernel32.SetErrorMode.restype = wintypes.UINT

cfgmgr32.CM_Get_Parent.argtypes = [ctypes.POINTER(wintypes.DWORD), wintypes.DWORD, wintypes.ULONG]
cfgmgr32.CM_Get_Device_IDW.argtypes = [wintypes.DWORD, wintypes.LPWSTR, wintypes.ULONG, wintypes.ULONG]
cfgmgr32.CM_Get_DevNode_Registry_PropertyW.argtypes = [
    wintypes.DWORD, wintypes.ULONG, ctypes.POINTER(wintypes.ULONG), ctypes.c_void_p,
    ctypes.POINTER(wintypes.ULONG), wintypes.ULONG]
cfgmgr32.CM_Locate_DevNodeW.argtypes = [ctypes.POINTER(wintypes.DWORD), wintypes.LPCWSTR, wintypes.ULONG]
cfgmgr32.CM_Request_Device_EjectW.argtypes = [wintypes.DWORD, ctypes.POINTER(ctypes.c_int),
                                              wintypes.LPWSTR, wintypes.ULONG, wintypes.ULONG]


# ------------------------------------------------------------------ outils bas niveau
def _ouvrir(chemin: str):
    h = kernel32.CreateFileW(chemin, 0, FILE_SHARE_RW, None, OPEN_EXISTING, 0, None)
    return None if h in (None, INVALID_HANDLE) else h


def _ioctl(h, code: int, entree: bytes = b"", taille_sortie: int = 1024) -> bytes | None:
    sortie = ctypes.create_string_buffer(taille_sortie)
    lus = wintypes.DWORD()
    tampon_entree = ctypes.create_string_buffer(entree, len(entree)) if entree else None
    ok = kernel32.DeviceIoControl(h, code, tampon_entree, len(entree), sortie, taille_sortie,
                                  ctypes.byref(lus), None)
    return sortie.raw[:lus.value] if ok else None


def _numero(h) -> tuple[int, int] | None:
    """(type de périphérique, numéro de disque)."""
    r = _ioctl(h, IOCTL_STORAGE_GET_DEVICE_NUMBER, taille_sortie=12)
    if not r or len(r) < 8:
        return None
    type_, numero = struct.unpack_from("<II", r)
    return type_, numero


def _chaine(brut: bytes, decalage: int) -> str:
    if not decalage or decalage >= len(brut):
        return ""
    fin = brut.find(b"\0", decalage)
    return brut[decalage:fin if fin >= 0 else None].decode("ascii", "replace").strip()


def _description(h) -> dict:
    """STORAGE_DEVICE_DESCRIPTOR : bus, support amovible, fabricant, modèle."""
    requete = struct.pack("<II4x", 0, 0)        # StorageDeviceProperty, PropertyStandardQuery
    r = _ioctl(h, IOCTL_STORAGE_QUERY_PROPERTY, requete, 1024)
    if not r or len(r) < 32:
        return {}
    (_v, _t, _type, _mod, amovible, _cq, o_fab, o_mod, _o_rev, o_serie, bus) = \
        struct.unpack_from("<IIBBBBIIIII", r)
    return {"bus": BUS.get(bus, str(bus)), "support_amovible": bool(amovible),
            "fabricant": _chaine(r, o_fab), "modele": _chaine(r, o_mod), "serie": _chaine(r, o_serie)}


def _taille(h) -> int:
    r = _ioctl(h, IOCTL_DISK_GET_DRIVE_GEOMETRY_EX, taille_sortie=256)
    if not r or len(r) < 32:
        return 0                                   # lecteur de cartes vide : pas de support
    return struct.unpack_from("<q", r, 24)[0]


def _id(devinst: int) -> str:
    tampon = ctypes.create_unicode_buffer(512)
    if cfgmgr32.CM_Get_Device_IDW(devinst, tampon, 512, 0) != CR_SUCCESS:
        return ""
    return tampon.value


def _propriete(devinst: int, prop: int):
    taille = wintypes.ULONG(0)
    type_ = wintypes.ULONG(0)
    cfgmgr32.CM_Get_DevNode_Registry_PropertyW(devinst, prop, ctypes.byref(type_), None,
                                               ctypes.byref(taille), 0)
    if not taille.value:
        return None
    tampon = ctypes.create_string_buffer(taille.value)
    if cfgmgr32.CM_Get_DevNode_Registry_PropertyW(devinst, prop, ctypes.byref(type_), tampon,
                                                  ctypes.byref(taille), 0) != CR_SUCCESS:
        return None
    if type_.value == 4:                           # REG_DWORD
        return struct.unpack_from("<I", tampon.raw)[0]
    return tampon.raw[:taille.value].decode("utf-16-le", "replace").split("\0")[0]


def _parent(devinst: int) -> int | None:
    p = wintypes.DWORD()
    return p.value if cfgmgr32.CM_Get_Parent(ctypes.byref(p), devinst, 0) == CR_SUCCESS else None


def _ancetre_amovible(devinst: int) -> int | None:
    """Premier nœud amovible en remontant depuis le disque : celui qu'on éjecte."""
    n, garde = devinst, 0
    while n is not None and garde < 16:
        caps = _propriete(n, CM_DRP_CAPABILITIES)
        if isinstance(caps, int) and caps & CM_DEVCAP_REMOVABLE:
            return n
        n, garde = _parent(n), garde + 1
    return None


def _disques_physiques():
    """[(numéro de disque, DevInst, chemin d'interface)] des disques présents."""
    hdev = setupapi.SetupDiGetClassDevsW(ctypes.byref(GUID_DEVINTERFACE_DISK), None, None,
                                         DIGCF_PRESENT | DIGCF_DEVICEINTERFACE)
    if hdev in (None, INVALID_HANDLE):
        return []
    trouves = []
    try:
        i = 0
        while True:
            itf = SP_DEVICE_INTERFACE_DATA()
            itf.cbSize = ctypes.sizeof(itf)
            if not setupapi.SetupDiEnumDeviceInterfaces(hdev, None, ctypes.byref(GUID_DEVINTERFACE_DISK),
                                                        i, ctypes.byref(itf)):
                break
            i += 1
            requis = wintypes.DWORD(0)
            setupapi.SetupDiGetDeviceInterfaceDetailW(hdev, ctypes.byref(itf), None, 0,
                                                      ctypes.byref(requis), None)
            if not requis.value:
                continue
            tampon = ctypes.create_string_buffer(requis.value)
            # cbSize de SP_DEVICE_INTERFACE_DETAIL_DATA_W : 8 en 64 bits, 6 en 32 bits
            struct.pack_into("<I", tampon, 0, 8 if ctypes.sizeof(ctypes.c_void_p) == 8 else 6)
            info = SP_DEVINFO_DATA()
            info.cbSize = ctypes.sizeof(info)
            if not setupapi.SetupDiGetDeviceInterfaceDetailW(hdev, ctypes.byref(itf), tampon, requis,
                                                             None, ctypes.byref(info)):
                continue
            chemin = ctypes.wstring_at(ctypes.addressof(tampon) + 4)
            h = _ouvrir(chemin)
            if not h:
                continue
            try:
                num = _numero(h)
                desc = _description(h)
                taille = _taille(h)
            finally:
                kernel32.CloseHandle(h)
            if num:
                trouves.append((num[1], info.DevInst, desc, taille))
    finally:
        setupapi.SetupDiDestroyDeviceInfoList(hdev)
    return trouves


def _lettres_par_disque() -> dict[int, list[tuple[str, str]]]:
    """{numéro de disque: [(lettre, nom du volume)]}."""
    ancien = kernel32.SetErrorMode(0x1 | 0x8000)     # pas de boîte « insérez un disque »
    resultat: dict[int, list[tuple[str, str]]] = {}
    try:
        masque = kernel32.GetLogicalDrives()
        for i, lettre in enumerate(string.ascii_uppercase):
            if not masque & (1 << i):
                continue
            racine = f"{lettre}:\\"
            if kernel32.GetDriveTypeW(racine) not in (DRIVE_REMOVABLE, DRIVE_FIXED):
                continue
            h = _ouvrir(f"\\\\.\\{lettre}:")
            if not h:
                continue
            try:
                num = _numero(h)
            finally:
                kernel32.CloseHandle(h)
            if not num or num[0] != FILE_DEVICE_DISK:
                continue
            nom = ctypes.create_unicode_buffer(261)
            if not kernel32.GetVolumeInformationW(racine, nom, 261, None, None, None, None, 0):
                nom.value = ""
            resultat.setdefault(num[1], []).append((lettre, nom.value))
    finally:
        kernel32.SetErrorMode(ancien)
    return resultat


def _lettre_systeme() -> str:
    t = ctypes.create_unicode_buffer(261)
    kernel32.GetSystemWindowsDirectoryW(t, 261)
    return (t.value[:1] or "C").upper()


# ------------------------------------------------------------------ interface publique
def lister() -> list[Disque]:
    """Tous les disques présents, internes compris (le tri se fait dans peripheriques.py)."""
    lettres = _lettres_par_disque()
    systeme = _lettre_systeme()
    disques = []
    for numero, devinst, desc, taille in _disques_physiques():
        ancetre = _ancetre_amovible(devinst)
        vols = lettres.get(numero, [])
        nom = (_propriete(devinst, CM_DRP_FRIENDLYNAME) or _propriete(devinst, CM_DRP_DEVICEDESC)
               or " ".join(x for x in (desc.get("fabricant"), desc.get("modele")) if x) or f"Disque {numero}")
        disques.append(Disque(
            numero=numero,
            nom=str(nom),
            bus=desc.get("bus", "?"),
            taille=taille,
            lettres=[l for l, _ in vols],
            volumes=[v for _, v in vols],
            id_disque=_id(devinst),
            id_ejectable=_id(ancetre) if ancetre is not None else "",
            id_parent=_id(_parent(ancetre)) if ancetre is not None and _parent(ancetre) is not None else "",
            support_amovible=desc.get("support_amovible", False),
            systeme=systeme in [l for l, _ in vols],
        ))
    return disques


def ejecter(id_ejectable: str) -> tuple[int, str]:
    """(type de veto, nom du veto). (0, "") = éjecté."""
    devinst = wintypes.DWORD()
    if cfgmgr32.CM_Locate_DevNodeW(ctypes.byref(devinst), id_ejectable, 0) != CR_SUCCESS:
        return 13, id_ejectable                     # déjà retiré
    veto = ctypes.c_int(0)
    nom = ctypes.create_unicode_buffer(520)
    r = cfgmgr32.CM_Request_Device_EjectW(devinst.value, ctypes.byref(veto), nom, 520, 0)
    if r == CR_SUCCESS and veto.value == 0:
        return 0, ""
    return (veto.value or -r), nom.value
