"""Gestes administrateur : remonter, forcer l'éjection, chercher les coupables partout.

Conception (après audit de sécurité de la 0.2.0) :

* AUCUNE tâche planifiée ni service : chaque geste passe par une fenêtre UAC. Une tâche à
  privilèges élevés qui lance du code installé dans le profil de l'utilisateur serait un
  contournement permanent de l'UAC : n'importe quel programme de la session pourrait
  modifier ce code puis lancer la tâche.
* Aucun fichier d'échange : Pipit ouvre un canal nommé au nom aléatoire et le processus
  élevé y répond. Clé aléatoire à usage unique (défi HMAC de multiprocessing.connection)
  ET vérification des deux bouts : Pipit n'accepte que le processus élevé qu'il vient de
  lancer (GetNamedPipeClientProcessId), et le processus élevé ne parle qu'au Pipit qui l'a
  lancé (GetNamedPipeServerProcessId). La clé seule ne suffit pas : la ligne de commande
  d'un processus élevé peut se lire depuis la session (PROCESS_QUERY_LIMITED_INFORMATION).
  Messages en JSON (recv_bytes), jamais pickle.
* Le processus élevé ne croit pas ce qu'on lui envoie : il ne reçoit qu'une action, un
  identifiant de périphérique et une valeur au format strict (deux lettres, 0 ou 1), recalcule lui-même le périphérique et ses lettres, et
  refuse tout ce qui n'est pas un périphérique externe éjectable (forcer, coupables,
  lettre — seulement une lettre de ce périphérique —, courant) ou
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
ACTIONS = ("remonter", "forcer", "coupables", "lettre", "courant")
# valeur jointe à la demande : « - » sauf lettre (ancienne + nouvelle, « EK ») et courant (« 1 » / « 0 »)
_VALEURS = {"lettre": re.compile(r"^[D-Z]{2}$"), "courant": re.compile(r"^[01]$")}
_ID_VALIDE = re.compile(r"^(USB|USBSTOR|SCSI|SD|STORAGE|1394|SBP2)\\[\w&#.{}\-\\]{3,200}$", re.I)
_CANAL = re.compile(r"^\\\\\.\\pipe\\pipit-[0-9a-f]{32}$")


def id_valide(ident: str) -> bool:
    return bool(_ID_VALIDE.match(ident or ""))


def valeur_valide(action: str, valeur: str) -> bool:
    motif = _VALEURS.get(action)
    return bool(motif.match(valeur or "")) if motif else valeur == "-"


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
    lance = _lancer_eleve(programme, parametres)
    if lance is None:
        return None
    return _attendre_processus(lance[0], attendre)


def _attendre_processus(h, attendre: float) -> int:
    from ctypes import wintypes
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    k32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    k32.CloseHandle.argtypes = [wintypes.HANDLE]
    k32.WaitForSingleObject(h, int(attendre * 1000))
    code = wintypes.DWORD(1)
    k32.GetExitCodeProcess(h, ctypes.byref(code))
    k32.CloseHandle(h)
    return code.value


def _lancer_eleve(programme: str, parametres: str):
    """(poignée du processus, pid) ou None si l'UAC est refusé."""
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
    k32.GetProcessId.argtypes = [wintypes.HANDLE]
    return info.hProcess, k32.GetProcessId(info.hProcess)


def _pid_du_bout(conn, cote: str) -> int:
    """Pid du client (côté Pipit) ou du serveur (côté élevé) d'un canal nommé."""
    from ctypes import wintypes
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    fonction = k32.GetNamedPipeClientProcessId if cote == "client" else k32.GetNamedPipeServerProcessId
    fonction.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.ULONG)]
    pid = wintypes.ULONG(0)
    return pid.value if fonction(conn.fileno(), ctypes.byref(pid)) else -1


# ------------------------------------------------------------------ côté Pipit : demander
_un_a_la_fois = threading.Lock()


def demander(action: str, ident: str, valeur: str = "-", delai: float = 120.0) -> dict:
    """Lance le processus élevé (fenêtre UAC) et attend sa réponse par le canal privé."""
    if action not in ACTIONS or not id_valide(ident) or not valeur_valide(action, valeur):
        return {"ok": False, "detail": "demande invalide"}
    if os.environ.get("PIPIT_DEMO") == "1" or sys.platform != "win32":
        from . import demo
        return demo.assistant(action, ident, valeur)
    import json
    import time
    from multiprocessing.connection import Client, Listener
    with _un_a_la_fois:
        canal = "\\\\.\\pipe\\pipit-" + secrets.token_hex(16)
        cle = secrets.token_bytes(32)
        try:
            ecoute = Listener(address=canal, family="AF_PIPE", authkey=cle)
        except OSError as exc:
            return {"ok": False, "detail": f"canal: {exc}"}
        try:
            script = Path(__file__).resolve().parent.parent / "run.py"
            args = subprocess.list2cmdline([str(script), "--assistant", action, ident, valeur, canal, cle.hex(),
                                            str(os.getpid())])
            lance = _lancer_eleve(systeme.executable_fenetre(), args)
            if lance is None:
                return {"ok": False, "detail": "uac_refuse"}
            h_proc, pid_eleve = lance
            reponse: dict = {}
            fin = time.time() + delai

            def attendre_reponse():
                # n'accepte QUE le processus élevé lancé à l'instant ; les autres sont congédiés
                while time.time() < fin and not reponse:
                    try:
                        conn = ecoute.accept()
                    except Exception:               # noqa: BLE001 — défi raté, canal fermé
                        if time.time() >= fin:
                            return
                        continue
                    with conn:
                        if _pid_du_bout(conn, "client") != pid_eleve:
                            continue
                        try:
                            if conn.poll(max(0.0, fin - time.time())):
                                donnees = json.loads(conn.recv_bytes(1 << 20).decode("utf-8"))
                                if isinstance(donnees, dict):
                                    reponse.update(donnees)
                                    reponse.setdefault("ok", False)
                        except Exception:           # noqa: BLE001
                            pass
                    return

            fil = threading.Thread(target=attendre_reponse, daemon=True, name="pipit-canal")
            fil.start()
            code = _attendre_processus(h_proc, delai)
            fil.join(3)
            if fil.is_alive():                       # personne ne s'est présenté : on débloque accept()
                fin = 0
                try:
                    Client(canal, family="AF_PIPE", authkey=cle).close()
                except Exception:                   # noqa: BLE001
                    pass
                fil.join(2)
            return dict(reponse) or {"ok": False, "detail": f"sans réponse (code {code})"}
        finally:
            ecoute.close()


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


def traiter(action: str, ident: str, valeur: str = "-") -> dict:
    if action not in ACTIONS or not id_valide(ident) or not valeur_valide(action, valeur):
        return {"ok": False, "detail": "demande invalide"}
    if action == "remonter":
        from . import admin_windows
        if not admin_windows.en_attente_de_retrait(ident):
            return {"ok": False, "detail": "etat"}       # jamais un périphérique désactivé exprès
        return admin_windows.remonter(ident)
    p = _peripherique(ident, exiger_lettres=(action in ("coupables", "lettre")))
    if p is None:
        return {"ok": False, "detail": "peripherique"}
    if action == "lettre":
        ancienne, nouvelle = valeur[0], valeur[1]
        if ancienne not in p.lettres or nouvelle == ancienne:
            return {"ok": False, "detail": "lettre"}   # seulement une lettre de CE périphérique
        from . import admin_windows
        return admin_windows.changer_lettre(ancienne, nouvelle)
    if action == "courant":
        from . import usb
        return usb.regler_courant(p.id, valeur == "1")
    if action == "forcer":
        from . import admin_windows
        return admin_windows.forcer(p.id, p.lettres)
    from . import poignees
    trouves = poignees.chercher(p.lettres)
    if trouves is None:
        return {"ok": False, "detail": "delai"}
    return {"ok": True, "coupables": [c.__dict__ for c in trouves]}


def executer(arguments: list[str]) -> int:
    """run.py --assistant <action> <identifiant> <valeur> <canal> <clé> <pid de Pipit> :
    processus élevé, une seule demande, réponse au seul Pipit qui l'a lancé."""
    if len(arguments) != 6:
        return 2
    action, ident, valeur, canal, cle_hex, pid_pipit = arguments
    if not _CANAL.match(canal) or not re.fullmatch(r"[0-9a-f]{64}", cle_hex) or not pid_pipit.isdigit():
        return 2
    try:
        r = traiter(action, ident, valeur)
    except Exception as exc:                        # noqa: BLE001
        r = {"ok": False, "detail": f"{type(exc).__name__}: {exc}"}
    import json
    from multiprocessing.connection import Client
    try:
        with Client(canal, family="AF_PIPE", authkey=bytes.fromhex(cle_hex)) as conn:
            if _pid_du_bout(conn, "serveur") != int(pid_pipit):
                return 4                            # un autre programme a pris la place du canal
            conn.send_bytes(json.dumps(r, ensure_ascii=False).encode("utf-8"))
    except Exception:                               # noqa: BLE001 — Pipit a abandonné entre-temps
        return 3
    return 0 if r.get("ok") else 1
