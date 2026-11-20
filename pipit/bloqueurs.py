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
from dataclasses import dataclass

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

    @property
    def fermable(self) -> bool:
        return self.programme.lower() not in INTOUCHABLES and self.pid > 4

    @property
    def patienter(self) -> bool:
        return self.programme.lower() in ATTENDRE

    @property
    def explorateur(self) -> bool:
        return self.programme.lower() == "explorer.exe"


def analyser(evenements: list[dict]) -> list[Bloqueur]:
    """Extrait (pid, programme) des événements 225, quels que soient les noms des champs
    (ils ont changé d'une version de Windows à l'autre)."""
    trouves: dict[int, Bloqueur] = {}
    for ev in evenements or []:
        donnees = ev.get("donnees") or {}
        chemin, pid = "", 0
        for nom, valeur in donnees.items():
            v = str(valeur or "")
            if v.lower().endswith(".exe") and not chemin:
                chemin = v
            elif "process" in str(nom).lower() and "id" in str(nom).lower() and v.isdigit():
                pid = int(v)
        if not pid:
            nombres = [int(str(v)) for v in donnees.values() if str(v or "").isdigit()]
            pid = nombres[0] if nombres else 0
        if chemin or pid:
            nom_exe = chemin.replace("/", "\\").rsplit("\\", 1)[-1] or "?"
            trouves[pid] = Bloqueur(pid, nom_exe, chemin)
    return list(trouves.values())


def _sans_console() -> dict:
    return {"creationflags": 0x08000000} if sys.platform == "win32" else {}


def chercher(depuis: float, lettres: list[str] | None = None) -> list[Bloqueur]:
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
    return analyser(evenements)


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
