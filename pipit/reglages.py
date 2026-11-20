"""Réglages de Pipit (fichier JSON dans le dossier des données)."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field

from . import systeme


@dataclass
class Reglages:
    masques: list[str] = field(default_factory=list)     # USB\VID_xxxx&PID_yyyy des périphériques cachés
    noms: dict[str, str] = field(default_factory=dict)   # même clé → nom choisi
    raccourci_menu: str = "Win+Alt"       # repris d'USB Safely Remove
    raccourci_tout: str = ""              # aucun par défaut
    notifier: bool = True
    demander_lecteur_cartes: bool = True
    internes_a_chaud: bool = False
    demarrage_propose: bool = False
    theme: str = "sombre"                 # « clair » ou « sombre » ; jamais le thème de Windows
    icones: dict[str, str] = field(default_factory=dict)   # matériel → image choisie (dossier des données)
    types: dict[str, str] = field(default_factory=dict)    # matériel → type corrigé à la main
    appareils: bool = True                # téléphones, tablettes, appareils photo
    compteur: bool = True                 # nombre de périphériques sur l'icône
    rappel_fermeture: bool = False        # prévenir à la fermeture de session s'il reste des périphériques


def _fichier():
    return systeme.dossier_donnees() / "reglages.json"


def charger() -> Reglages:
    try:
        donnees = json.loads(_fichier().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return Reglages()
    connus = {k: v for k, v in donnees.items() if k in Reglages.__dataclass_fields__}
    try:
        return Reglages(**connus)
    except TypeError:
        return Reglages()


def enregistrer(r: Reglages) -> None:
    f = _fichier()
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(asdict(r), ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(f)
