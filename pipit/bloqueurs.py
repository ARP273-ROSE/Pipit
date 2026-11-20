"""Qui empêche l'éjection ?

Quand un programme garde un fichier ouvert sur la clé, Windows refuse
l'éjection ET note dans son journal (Microsoft-Windows-Kernel-PnP/Configuration,
événement 225) le chemin et le numéro du programme. Ce journal se lit sans
droits d'administrateur : pas besoin d'un pilote pour fouiller les fichiers ouverts.
"""
from __future__ import annotations

import datetime
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field

# Programmes qu'on ne propose jamais de fermer : le système, l'Explorateur (le bureau
# entier disparaîtrait), les antivirus et l'indexation, qui lâchent prise d'eux-mêmes.
INTOUCHABLES = {"system", "explorer.exe", "svchost.exe", "csrss.exe", "services.exe", "lsass.exe",
                "wininit.exe", "smss.exe", "dwm.exe", "msmpeng.exe", "searchindexer.exe",
                "searchprotocolhost.exe", "searchfilterhost.exe", "bdservicehost.exe", "bdagent.exe",
                "vsserv.exe", "bdredline.exe", "mssense.exe"}
ATTENDRE = {"msmpeng.exe", "searchindexer.exe", "searchprotocolhost.exe", "searchfilterhost.exe",
            "bdservicehost.exe", "bdagent.exe", "vsserv.exe", "bdredline.exe", "mssense.exe"}

PS = r"""
$ErrorActionPreference = 'SilentlyContinue'
$debut = [DateTime]::Parse('{debut}').ToLocalTime()
$evs = Get-WinEvent -FilterHashtable @{{LogName='Microsoft-Windows-Kernel-PnP/Configuration'; Id=225; StartTime=$debut}} -MaxEvents 20
$sortie = @()
foreach ($e in $evs) {{
  $x = [xml]$e.ToXml()
  $donnees = @{{}}
  foreach ($d in $x.Event.EventData.Data) {{ $donnees[$d.Name] = $d.'#text' }}
  $sortie += [pscustomobject]@{{ quand = $e.TimeCreated.ToString('o'); donnees = $donnees }}
}}
ConvertTo-Json -InputObject @($sortie) -Depth 4 -Compress
"""


@dataclass
class Bloqueur:
    pid: int
    programme: str        # nom du fichier, ex. « WINWORD.EXE »
    chemin: str = ""
    fichiers: list = field(default_factory=list)   # fichiers ouverts sur le périphérique, s'ils sont connus

    @property
    def fermable(self) -> bool:
        return self.programme.lower() not in INTOUCHABLES and self.pid > 4

    @property
    def patienter(self) -> bool:
        return self.programme.lower() in ATTENDRE

    @property
    def explorateur(self) -> bool:
        return self.programme.lower() == "explorer.exe"


def analyser(evenements: list[dict], ids: list[str] | None = None) -> list[Bloqueur]:
    """Extrait (pid, programme) des événements 225, quels que soient les noms des champs
    (ils ont changé d'une version de Windows à l'autre). Avec `ids`, ne garde que les
    événements qui citent ce périphérique (un autre périphérique éjecté au même moment
    ne doit pas désigner son propre coupable). Jamais de numéro de programme deviné."""
    ids_maj = [i.upper() for i in (ids or []) if i]
    trouves: dict[int, Bloqueur] = {}
    for ev in evenements or []:
        donnees = ev.get("donnees") or {}
        valeurs = [str(v or "") for v in donnees.values()]
        if ids_maj and any("\\" in v and "_" in v for v in valeurs):
            # l'événement cite un périphérique : est-ce le nôtre (ou un de ses enfants) ?
            if not any(v.upper().startswith(i) or i.startswith(v.upper()) for v in valeurs
                       for i in ids_maj if "\\" in v and len(v) > 8):
                continue
        chemin, pid = "", 0
        for nom, valeur in donnees.items():
            v = str(valeur or "")
            if v.lower().endswith(".exe") and not chemin:
                chemin = v
            elif "process" in str(nom).lower() and "id" in str(nom).lower() and v.isdigit():
                pid = int(v)
        if chemin and pid:
            nom_exe = chemin.replace("/", "\\").rsplit("\\", 1)[-1] or "?"
            trouves[pid] = Bloqueur(pid, nom_exe, chemin)
    return list(trouves.values())


def _sans_console() -> dict:
    return {"creationflags": 0x08000000} if sys.platform == "win32" else {}


def chercher(depuis: float, lettres: list[str] | None = None, ids: list[str] | None = None) -> list[Bloqueur]:
    if os.environ.get("PIPIT_DEMO") == "1" or sys.platform != "win32":
        from . import demo
        return demo.bloqueurs()
    debut = datetime.datetime.fromtimestamp(depuis, datetime.timezone.utc).isoformat()
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                            PS.format(debut=debut)],
                           capture_output=True, timeout=20, **_sans_console())
        texte = r.stdout.decode("utf-8", "replace").strip()
        evenements = json.loads(texte) if texte else []
    except (OSError, subprocess.SubprocessError, ValueError):
        return []
    if isinstance(evenements, dict):
        evenements = [evenements]
    return analyser(evenements, ids)


def fermer(b: Bloqueur) -> bool:
    """Demande poliment au programme de se fermer (comme la croix de sa fenêtre) : il peut
    proposer d'enregistrer. Jamais de fermeture forcée."""
    if not b.fermable:
        return False
    if os.environ.get("PIPIT_DEMO") == "1" or sys.platform != "win32":
        return True
    try:
        r = subprocess.run(["taskkill", "/PID", str(b.pid)], capture_output=True, timeout=15,
                           **_sans_console())
        return r.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def montrer(pid: int) -> bool:
    """Met au premier plan la fenêtre du programme (pour enregistrer et fermer soi-même)."""
    if sys.platform != "win32" or os.environ.get("PIPIT_DEMO") == "1":
        return os.environ.get("PIPIT_DEMO") == "1"
    import ctypes
    from ctypes import wintypes
    u = ctypes.windll.user32
    trouvees = []
    PROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def rappel(hwnd, _l):
        proprietaire = wintypes.DWORD()
        u.GetWindowThreadProcessId(hwnd, ctypes.byref(proprietaire))
        if proprietaire.value == pid and u.IsWindowVisible(hwnd) and u.GetWindowTextLengthW(hwnd) > 0:
            trouvees.append(hwnd)
        return True

    u.EnumWindows(PROC(rappel), 0)
    if not trouvees:
        return False
    hwnd = trouvees[0]
    if u.IsIconic(hwnd):
        u.ShowWindow(hwnd, 9)                  # SW_RESTORE
    return bool(u.SetForegroundWindow(hwnd))
