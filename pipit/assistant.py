"""Assistant administrateur : remonter, forcer l'éjection, chercher les coupables partout.

USB Safely Remove a un service système pour ces gestes. Pipit utilise une tâche planifiée
« Pipit\\Assistant », créée une fois (une fenêtre UAC) avec les privilèges les plus élevés
de l'utilisateur : la lancer ensuite (schtasks /run) ne redemande rien. Elle ne tourne que
le temps d'une demande, puis s'arrête.

Échange par fichiers dans le dossier des données (le même utilisateur) :
    assistant/demande-<n>.json   {"action": ..., "id": ..., "lettres": [...]}
    assistant/reponse-<n>.json
L'assistant n'exécute que trois actions fixes, sur un identifiant de périphérique
vérifié : jamais une commande venue du fichier.

Sans la tâche (refusée, ou poste sans droits), chaque geste passe par une fenêtre UAC.
"""
from __future__ import annotations

import ctypes
import json
import os
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path

from . import systeme

TACHE = "Pipit\\Assistant"
ACTIONS = ("remonter", "forcer", "coupables", "fermer_fichiers")
_ID_VALIDE = re.compile(r"^(USB|USBSTOR|SCSI|SD|SWD|STORAGE|PCI|HID|BTHENUM|1394|SBP2)[\\\w&#.{}\-]*$", re.I)


def dossier() -> Path:
    d = systeme.dossier_donnees() / "assistant"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _sans_console() -> dict:
    return {"creationflags": 0x08000000} if sys.platform == "win32" else {}


def _commande() -> tuple[str, str]:
    script = Path(__file__).resolve().parent.parent / "run.py"
    return systeme.executable_fenetre(), subprocess.list2cmdline([str(script), "--assistant"])


# ------------------------------------------------------------------ installation de la tâche
def installe() -> bool:
    if sys.platform != "win32":
        return False
    r = subprocess.run(["schtasks", "/query", "/tn", TACHE], capture_output=True, **_sans_console())
    return r.returncode == 0


def xml_tache() -> str:
    exe, args = _commande()
    dossier_app = str(Path(__file__).resolve().parent.parent)
    from xml.sax.saxutils import escape
    return f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo><Description>Pipit : remonter un périphérique, forcer une éjection (sur demande seulement).</Description></RegistrationInfo>
  <Principals><Principal id="Author"><LogonType>InteractiveToken</LogonType><RunLevel>HighestAvailable</RunLevel></Principal></Principals>
  <Settings>
    <MultipleInstancesPolicy>Queue</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <ExecutionTimeLimit>PT5M</ExecutionTimeLimit>
    <Priority>5</Priority>
  </Settings>
  <Actions Context="Author"><Exec><Command>{escape(exe)}</Command><Arguments>{escape(args)}</Arguments><WorkingDirectory>{escape(dossier_app)}</WorkingDirectory></Exec></Actions>
</Task>
"""


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
    info.fMask = 0x40                                  # SEE_MASK_NOCLOSEPROCESS
    info.lpVerb, info.lpFile, info.lpParameters, info.nShow = "runas", programme, parametres, 0
    if not ctypes.windll.shell32.ShellExecuteExW(ctypes.byref(info)) or not info.hProcess:
        return None
    k32 = ctypes.windll.kernel32
    k32.WaitForSingleObject(wintypes.HANDLE(info.hProcess), int(attendre * 1000))
    code = wintypes.DWORD(1)
    k32.GetExitCodeProcess(wintypes.HANDLE(info.hProcess), ctypes.byref(code))
    k32.CloseHandle(wintypes.HANDLE(info.hProcess))
    return code.value


def installer() -> bool:
    """Crée la tâche (une fenêtre UAC). True si elle existe ensuite."""
    if sys.platform != "win32":
        return False
    xml = dossier() / "tache.xml"
    xml.write_text(xml_tache(), encoding="utf-16")
    _executer_eleve("schtasks", subprocess.list2cmdline(["/create", "/f", "/tn", TACHE, "/xml", str(xml)]), 60)
    return installe()


def desinstaller() -> bool:
    if not installe():
        return True
    _executer_eleve("schtasks", subprocess.list2cmdline(["/delete", "/f", "/tn", TACHE]), 60)
    return not installe()


# ------------------------------------------------------------------ côté Pipit : demander
def demander(action: str, ident: str, lettres: list[str] | None = None, delai: float = 90.0) -> dict:
    """Envoie une demande à l'assistant et attend sa réponse."""
    if action not in ACTIONS or not _ID_VALIDE.match(ident or ""):
        return {"ok": False, "detail": "demande invalide"}
    if os.environ.get("PIPIT_DEMO") == "1" or sys.platform != "win32":
        from . import demo
        return demo.assistant(action, ident, lettres or [])
    n = uuid.uuid4().hex
    demande = dossier() / f"demande-{n}.json"
    reponse = dossier() / f"reponse-{n}.json"
    demande.write_text(json.dumps({"action": action, "id": ident, "lettres": lettres or []}), encoding="utf-8")
    lance = False
    if installe():
        r = subprocess.run(["schtasks", "/run", "/tn", TACHE], capture_output=True, **_sans_console())
        lance = r.returncode == 0
    if not lance:
        exe, args = _commande()
        code = _executer_eleve(exe, args + " " + subprocess.list2cmdline([str(demande)]), delai)
        if code is None:
            demande.unlink(missing_ok=True)
            return {"ok": False, "detail": "uac_refuse"}
    fin = time.time() + delai
    while time.time() < fin:
        if reponse.exists():
            try:
                donnees = json.loads(reponse.read_text(encoding="utf-8"))
                reponse.unlink(missing_ok=True)
                return donnees
            except (OSError, ValueError):
                pass
        time.sleep(0.3)
    demande.unlink(missing_ok=True)
    return {"ok": False, "detail": "delai"}


# ------------------------------------------------------------------ côté assistant : exécuter
def _traiter(d: dict) -> dict:
    action, ident, lettres = d.get("action"), str(d.get("id", "")), [str(l)[:1].upper() for l in d.get("lettres", [])]
    if action not in ACTIONS or not _ID_VALIDE.match(ident):
        return {"ok": False, "detail": "demande invalide"}
    lettres = [l for l in lettres if l.isalpha()]
    if action in ("coupables", "fermer_fichiers"):
        from . import poignees
        trouves = poignees.chercher(lettres, fermer=(action == "fermer_fichiers"))
        if trouves is None:
            return {"ok": False, "detail": "delai"}
        return {"ok": True, "coupables": [c.__dict__ for c in trouves]}
    from . import admin_windows
    if action == "forcer":
        return admin_windows.forcer(ident, lettres)
    return admin_windows.remonter(ident)


def executer(fichier: str | None = None) -> int:
    """Point d'entrée de l'assistant (run.py --assistant) : traite les demandes en attente."""
    fichiers = [Path(fichier)] if fichier else sorted(dossier().glob("demande-*.json"))
    for f in fichiers:
        if not f.name.startswith("demande-") or f.parent.resolve() != dossier().resolve():
            continue
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        f.unlink(missing_ok=True)
        try:
            r = _traiter(d)
        except Exception as exc:                    # noqa: BLE001
            r = {"ok": False, "detail": f"{type(exc).__name__}: {exc}"}
        reponse = f.with_name(f.name.replace("demande-", "reponse-"))
        tmp = reponse.with_suffix(".tmp")
        tmp.write_text(json.dumps(r, ensure_ascii=False), encoding="utf-8")
        tmp.replace(reponse)
    return 0


def est_admin() -> bool:
    if sys.platform != "win32":
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:                               # noqa: BLE001
        return False
