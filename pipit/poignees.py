"""Qui a des fichiers ouverts sur un lecteur ? Inventaire des « poignées » (handles) ouvertes.

Sans pilote : NtQuerySystemInformation(SystemExtendedHandleInformation) liste toutes les
poignées du système ; on garde celles de type « fichier », on les copie chez nous
(DuplicateHandle) et on demande leur chemin (GetFinalPathNameByHandleW). Sans droits
d'administrateur on ne voit que ses propres programmes ; l'assistant administrateur
(assistant.py) voit tout, antivirus compris.

Certaines poignées (tubes nommés en attente) font geler les fonctions qui les
interrogent : on les écarte par leurs droits d'accès, comme le font les outils connus,
et l'appelant met de toute façon une limite de temps.
"""
from __future__ import annotations

import ctypes
import os
import sys
import threading
from ctypes import wintypes
from dataclasses import dataclass, field


@dataclass
class Coupable:
    pid: int
    programme: str
    chemin_programme: str = ""
    fichiers: list[str] = field(default_factory=list)


if sys.platform == "win32":
    ntdll = ctypes.WinDLL("ntdll")
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    class ENTREE(ctypes.Structure):
        _fields_ = [("Object", ctypes.c_void_p), ("UniqueProcessId", ctypes.c_size_t),
                    ("HandleValue", ctypes.c_size_t), ("GrantedAccess", wintypes.ULONG),
                    ("CreatorBackTraceIndex", wintypes.USHORT), ("ObjectTypeIndex", wintypes.USHORT),
                    ("HandleAttributes", wintypes.ULONG), ("Reserved", wintypes.ULONG)]

    ntdll.NtQuerySystemInformation.argtypes = [wintypes.ULONG, ctypes.c_void_p, wintypes.ULONG,
                                               ctypes.POINTER(wintypes.ULONG)]
    ntdll.NtQuerySystemInformation.restype = ctypes.c_long
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.DuplicateHandle.argtypes = [wintypes.HANDLE, wintypes.HANDLE, wintypes.HANDLE,
                                         ctypes.POINTER(wintypes.HANDLE), wintypes.DWORD, wintypes.BOOL,
                                         wintypes.DWORD]
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    kernel32.GetFileType.argtypes = [wintypes.HANDLE]
    kernel32.GetFinalPathNameByHandleW.argtypes = [wintypes.HANDLE, wintypes.LPWSTR, wintypes.DWORD,
                                                   wintypes.DWORD]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                                                    ctypes.POINTER(wintypes.DWORD)]
    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                                     wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]

SystemExtendedHandleInformation = 64
STATUS_INFO_LENGTH_MISMATCH = -1073741820       # 0xC0000004
PROCESS_DUP_HANDLE, PROCESS_QUERY_LIMITED = 0x40, 0x1000
DUPLICATE_CLOSE_SOURCE, DUPLICATE_SAME_ACCESS = 0x1, 0x2
FILE_TYPE_DISK = 1
# droits d'accès typiques des tubes synchrones qui bloquent GetFinalPathNameByHandle
ACCES_DANGEREUX = {0x0012019F, 0x001A019F, 0x00120189, 0x00100000, 0x0016019F}


def _entrees():
    taille = 1 << 20
    while True:
        tampon = ctypes.create_string_buffer(taille)
        requis = wintypes.ULONG(0)
        st = ntdll.NtQuerySystemInformation(SystemExtendedHandleInformation, tampon, taille,
                                            ctypes.byref(requis))
        if st == STATUS_INFO_LENGTH_MISMATCH:
            taille = max(taille * 2, requis.value + (1 << 16))
            if taille > (1 << 30):
                return []
            continue
        if st != 0:
            return []
        n = ctypes.c_size_t.from_buffer(tampon).value
        decalage = 2 * ctypes.sizeof(ctypes.c_size_t)
        tableau = (ENTREE * n).from_buffer(tampon, decalage)
        return list(tableau)


def _index_type_fichier(entrees) -> int | None:
    """Type d'objet « File » : on ouvre un fichier soi-même et on le retrouve dans la liste."""
    h = kernel32.CreateFileW(sys.executable, 0x80000000, 0x7, None, 3, 0, None)
    if not h or h == ctypes.c_void_p(-1).value:
        return None
    try:
        moi = os.getpid()
        for e in _entrees():
            if e.UniqueProcessId == moi and e.HandleValue == h:
                return e.ObjectTypeIndex
    finally:
        kernel32.CloseHandle(h)
    return None


def _nom_programme(pid: int) -> str:
    h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED, False, pid)
    if not h:
        return ""
    try:
        t = ctypes.create_unicode_buffer(1024)
        n = wintypes.DWORD(1024)
        if kernel32.QueryFullProcessImageNameW(h, 0, t, ctypes.byref(n)):
            return t.value
    finally:
        kernel32.CloseHandle(h)
    return ""


def _chemin(proc, valeur: int) -> str:
    moi = kernel32.GetCurrentProcess()
    copie = wintypes.HANDLE()
    if not kernel32.DuplicateHandle(proc, valeur, moi, ctypes.byref(copie), 0, False, DUPLICATE_SAME_ACCESS):
        return ""
    try:
        if kernel32.GetFileType(copie) != FILE_TYPE_DISK:
            return ""
        t = ctypes.create_unicode_buffer(1024)
        n = kernel32.GetFinalPathNameByHandleW(copie, t, 1024, 0)
        return t.value if 0 < n < 1024 else ""
    finally:
        kernel32.CloseHandle(copie)


def _sur_lecteur(chemin: str, lettres: set[str]) -> bool:
    c = chemin[4:] if chemin.startswith("\\\\?\\") else chemin
    return len(c) >= 2 and c[1] == ":" and c[0].upper() in lettres


def _chercher(lettres: set[str], fermer: bool) -> list[Coupable]:
    entrees = _entrees()
    type_fichier = _index_type_fichier(entrees)
    if type_fichier is None:
        return []
    moi = os.getpid()
    processus: dict[int, object] = {}
    trouves: dict[int, Coupable] = {}
    try:
        for e in entrees:
            pid = e.UniqueProcessId
            if (e.ObjectTypeIndex != type_fichier or pid in (0, 4, moi)
                    or e.GrantedAccess in ACCES_DANGEREUX):
                continue
            if pid not in processus:
                processus[pid] = kernel32.OpenProcess(PROCESS_DUP_HANDLE, False, pid) or None
            proc = processus[pid]
            if proc is None:
                continue
            chemin = _chemin(proc, e.HandleValue)
            if not chemin or not _sur_lecteur(chemin, lettres):
                continue
            c = trouves.get(pid)
            if c is None:
                exe = _nom_programme(pid)
                c = trouves[pid] = Coupable(pid, exe.rsplit("\\", 1)[-1] or "?", exe)
            c.fichiers.append(chemin[4:] if chemin.startswith("\\\\?\\") else chemin)
            if fermer:
                # « fermer seulement ses fichiers sur le périphérique » : la poignée est
                # refermée chez le programme lui-même (il peut s'en plaindre ensuite)
                bidon = wintypes.HANDLE()
                kernel32.DuplicateHandle(proc, e.HandleValue, None, ctypes.byref(bidon), 0, False,
                                         DUPLICATE_CLOSE_SOURCE)
    finally:
        for h in processus.values():
            if h:
                kernel32.CloseHandle(h)
    return filtrer(trouves.values())


def filtrer(coupables) -> list[Coupable]:
    """L'Explorateur surveille la racine de chaque lecteur (notifications de changement) et la
    lâche tout seul à l'éjection : ce n'est pas un coupable tant qu'il ne tient que la racine."""
    garde = [c for c in coupables
             if not (c.programme.lower() == "explorer.exe" and all(len(f.rstrip("\\")) <= 2 for f in c.fichiers))]
    return sorted(garde, key=lambda c: c.programme.lower())


def chercher(lettres: list[str], fermer: bool = False, delai: float = 20.0) -> list[Coupable] | None:
    """Programmes qui ont des fichiers ou dossiers ouverts sur ces lettres. None = pas pu
    savoir (pas Windows, délai dépassé). `fermer` referme ces poignées (assistant seulement)."""
    if os.environ.get("PIPIT_DEMO") == "1" or sys.platform != "win32":
        if os.environ.get("PIPIT_DEMO") == "1":
            return [Coupable(4242, "WINWORD.EXE", "C:\\Program Files\\Microsoft Office\\WINWORD.EXE",
                             [f"{(lettres or ['E'])[0]}:\\Rapport.docx"])]
        return None
    lettres_ok = {l.upper() for l in lettres if l}
    if not lettres_ok:
        return []
    resultat: list = [None]

    def travail():
        try:
            resultat[0] = _chercher(lettres_ok, fermer)
        except Exception:                       # noqa: BLE001 — mieux vaut « inconnu » qu'un plantage
            resultat[0] = None

    fil = threading.Thread(target=travail, daemon=True, name="pipit-poignees")
    fil.start()
    fil.join(delai)
    return resultat[0] if not fil.is_alive() else None
