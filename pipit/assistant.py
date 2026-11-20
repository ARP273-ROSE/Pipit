"""Gestes administrateur : remonter, forcer l'éjection, chercher les coupables partout.

Conception (après audit de sécurité de la 0.2.0) :

* AUCUNE tâche planifiée ni service : chaque geste passe par une fenêtre UAC. Une tâche à
  privilèges élevés qui lance du code installé dans le profil de l'utilisateur serait un
  contournement permanent de l'UAC : n'importe quel programme de la session pourrait
  modifier ce code puis lancer la tâche.
* Aucun fichier d'échange : Pipit ouvre un canal nommé au nom aléatoire et le processus
  élevé y répond. Les deux côtés s'authentifient par une clé aléatoire à usage unique
  (défi HMAC de multiprocessing.connection), transmise sur la ligne de commande du
  processus élevé, illisible pour un processus non élevé.
* Le processus élevé ne croit pas ce qu'on lui envoie : il ne reçoit qu'une action et un
  identifiant de périphérique, recalcule lui-même le périphérique et ses lettres, et
  refuse tout ce qui n'est pas un périphérique externe éjectable (forcer, coupables) ou
  un périphérique éjecté encore branché, problème 47 (remonter).
"""
from __future__ import annotations

import ctypes
import os
import re
import secrets
import subprocess
import sys
import threading
from pathlib import Path

from . import systeme

ANCIENNE_TACHE = "Pipit\\Assistant"          # créée par la 0.2.0 : retirée dès que possible
ACTIONS = ("remonter", "forcer", "coupables")
_ID_VALIDE = re.compile(r"^(USB|USBSTOR|SCSI|SD|STORAGE|1394|SBP2)\\[\w&#.{}\-\\]{3,200}$", re.I)
_CANAL = re.compile(r"^\\\\\.\\pipe\\pipit-[0-9a-f]{32}$")


def id_valide(ident: str) -> bool:
    return bool(_ID_VALIDE.match(ident or ""))


def _sans_console() -> dict:
    return {"creationflags": 0x08000000} if sys.platform == "win32" else {}


def est_admin() -> bool:
    if sys.platform != "win32":
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:                               # noqa: BLE001
        return False


# ------------------------------------------------------------------ ancienne tâche (0.2.0)
def ancienne_tache_presente() -> bool:
    if sys.platform != "win32":
        return False
    try:
        r = subprocess.run(["schtasks", "/query", "/tn", ANCIENNE_TACHE], capture_output=True, timeout=15,
                           **_sans_console())
        return r.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def retirer_ancienne_tache() -> bool:
    """La tâche de la 0.2.0 est un risque : on la supprime (une fenêtre UAC)."""
    if not ancienne_tache_presente():
        return True
    _executer_eleve("schtasks", subprocess.list2cmdline(["/delete", "/f", "/tn", ANCIENNE_TACHE]), 60)
    return not ancienne_tache_presente()


# ------------------------------------------------------------------ élévation
def _executer_eleve(programme: str, parametres: str, attendre: float = 120.0) -> int | None:
    """ShellExecuteEx « runas » : une fenêtre UAC ; renvoie le code de sortie (None = refusé)."""
    from ctypes import wintypes

    class SHELLEXECUTEINFOW(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("fMask", wintypes.ULONG), ("hwnd", wintypes.HWND),
                    ("lpVerb", wintypes.LPCWSTR), ("lpFile", wintypes.LPCWSTR),
                    ("lpParameters", wintypes.LPCWSTR), ("lpDirectory", wintypes.LPCWSTR),
                    ("nShow", ctypes.c_int), ("hInstApp", wintypes.HINSTANCE), ("lpIDList", ctypes.c_void_p),
                    ("lpClass", wintypes.LPCWSTR), ("hkeyClass", wintypes.HKEY), ("dwHotKey", wintypes.DWORD),
                    ("hIconOrMonitor", wintypes.HANDLE), ("hProcess", wintypes.HANDLE)]

    info = SHELLEXECUTEINFOW()
    info.cbSize = ctypes.sizeof(info)
    info.fMask = 0x40 | 0x400                          # NOCLOSEPROCESS | FLAG_NO_UI (pas de boîte d'erreur)
    info.lpVerb, info.lpFile, info.lpParameters, info.nShow = "runas", programme, parametres, 0
    shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    shell32.ShellExecuteExW.argtypes = [ctypes.POINTER(SHELLEXECUTEINFOW)]
    if not shell32.ShellExecuteExW(ctypes.byref(info)) or not info.hProcess:
        return None
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    k32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    k32.CloseHandle.argtypes = [wintypes.HANDLE]
    k32.WaitForSingleObject(info.hProcess, int(attendre * 1000))
    code = wintypes.DWORD(1)
    k32.GetExitCodeProcess(info.hProcess, ctypes.byref(code))
    k32.CloseHandle(info.hProcess)
    return code.value


# ------------------------------------------------------------------ côté Pipit : demander
_un_a_la_fois = threading.Lock()


def demander(action: str, ident: str, delai: float = 120.0) -> dict:
    """Lance le processus élevé (fenêtre UAC) et attend sa réponse par le canal privé."""
    if action not in ACTIONS or not id_valide(ident):
        return {"ok": False, "detail": "demande invalide"}
    if os.environ.get("PIPIT_DEMO") == "1" or sys.platform != "win32":
        from . import demo
        return demo.assistant(action, ident)
    from multiprocessing.connection import Client, Listener
    with _un_a_la_fois:
        canal = "\\\\.\\pipe\\pipit-" + secrets.token_hex(16)
        cle = secrets.token_bytes(32)
        try:
            ecoute = Listener(address=canal, family="AF_PIPE", authkey=cle)
        except OSError as exc:
            return {"ok": False, "detail": f"canal: {exc}"}
        reponse: dict = {}

        def attendre_reponse():
            try:
                with ecoute.accept() as conn:
                    if conn.poll(delai):
                        donnees = conn.recv()
                        if isinstance(donnees, dict):
                            reponse.update(donnees)
            except Exception:                       # noqa: BLE001 — authentification ratée, canal coupé
                pass

        fil = threading.Thread(target=attendre_reponse, daemon=True, name="pipit-canal")
        fil.start()
        script = Path(__file__).resolve().parent.parent / "run.py"
        args = subprocess.list2cmdline([str(script), "--assistant", action, ident, canal, cle.hex()])
        code = _executer_eleve(systeme.executable_fenetre(), args, delai)
        if fil.is_alive():                           # personne ne s'est connecté : on débloque accept()
            try:
                Client(canal, family="AF_PIPE", authkey=cle).close()
            except Exception:                       # noqa: BLE001
                pass
            fil.join(2)
        ecoute.close()
        if code is None:
            return {"ok": False, "detail": "uac_refuse"}
        return reponse or {"ok": False, "detail": f"sans réponse (code {code})"}


# ------------------------------------------------------------------ côté élevé : exécuter
def _peripherique(ident: str, exiger_lettres: bool):
    """Recalcule le périphérique à partir de l'identifiant seul : jamais les lettres reçues."""
    from . import disques_windows, peripheriques
    from .modele import regrouper
    for p in regrouper(disques_windows.lister()):
        if p.id.upper() != ident.upper():
            continue
        if any(d.systeme for d in p.disques) or p.bus not in peripheriques.BUS_EXTERNES or p.geste != "ejecter":
            return None
        if exiger_lettres and not p.lettres:
            return None
        return p
    return None


def traiter(action: str, ident: str) -> dict:
    if action not in ACTIONS or not id_valide(ident):
        return {"ok": False, "detail": "demande invalide"}
    if action == "remonter":
        from . import admin_windows
        if not admin_windows.en_attente_de_retrait(ident):
            return {"ok": False, "detail": "etat"}       # jamais un périphérique désactivé exprès
        return admin_windows.remonter(ident)
    p = _peripherique(ident, exiger_lettres=(action == "coupables"))
    if p is None:
        return {"ok": False, "detail": "peripherique"}
    if action == "forcer":
        from . import admin_windows
        return admin_windows.forcer(p.id, p.lettres)
    from . import poignees
    trouves = poignees.chercher(p.lettres)
    if trouves is None:
        return {"ok": False, "detail": "delai"}
    return {"ok": True, "coupables": [c.__dict__ for c in trouves]}


def executer(arguments: list[str]) -> int:
    """run.py --assistant <action> <identifiant> <canal> <clé> : processus élevé, une seule demande."""
    if len(arguments) != 4:
        return 2
    action, ident, canal, cle_hex = arguments
    if not _CANAL.match(canal) or not re.fullmatch(r"[0-9a-f]{64}", cle_hex):
        return 2
    try:
        r = traiter(action, ident)
    except Exception as exc:                        # noqa: BLE001
        r = {"ok": False, "detail": f"{type(exc).__name__}: {exc}"}
    from multiprocessing.connection import Client
    try:
        with Client(canal, family="AF_PIPE", authkey=bytes.fromhex(cle_hex)) as conn:
            conn.send(r)
    except Exception:                               # noqa: BLE001 — Pipit a abandonné entre-temps
        return 3
    return 0 if r.get("ok") else 1
