"""Apparence de Pipit : thème clair ou sombre, choisi dans les réglages.

Le standard du kit veut que l'application décide de son apparence, pas Windows : le
choix appartient à l'utilisateur (sombre par défaut, comme le menu qu'il avait avant),
jamais au thème du système. Vert olive du pipit des prés, rouge brique pour les alertes.
"""
from __future__ import annotations

from pathlib import Path

POLICES = Path(__file__).resolve().parent / "polices"

VERT = "#2E7D32"
ORANGE = "#B26A00"
ALERTE = "#B5382B"
GRIS = "#6B7785"

THEMES = {
    "clair": {
        "olive": "#4E6E2A", "olive_fonce": "#3A5420", "accent_doux": "#DCE8C8",
        "couleurs": {
            "fenetre": "#F4F6F2", "texte": "#1F2933", "base": "#FFFFFF", "base_alt": "#F3F6EE",
            "bouton": "#E9EEE4", "texte_bouton": "#1F2933", "selection": "#DCE8C8",
            "texte_selection": "#24331A", "lien": "#4E6E2A", "infobulle": "#FFFFFF",
            "texte_infobulle": "#1F2933", "desactive": "#98A2AE", "clair": "#FFFFFF",
            "moyen": "#C9D2C4", "sombre": "#9AA69A",
        },
        "cadre": "#D5DDD0", "fond_groupe": "#FFFFFF", "entete": "#EEF2EA", "survol": "#F8FBF2",
        "bouton_fond": "#FFFFFF", "bouton_bord": "#C2CCBC", "gris": "#6B7785",
    },
    "sombre": {
        "olive": "#7FA04A", "olive_fonce": "#5E7C33", "accent_doux": "#3A4A2A",
        "couleurs": {
            "fenetre": "#1E2124", "texte": "#E4E7EA", "base": "#26292D", "base_alt": "#2C3035",
            "bouton": "#2F3338", "texte_bouton": "#E4E7EA", "selection": "#4A5E30",
            "texte_selection": "#F2F6EC", "lien": "#A5C46E", "infobulle": "#2F3338",
            "texte_infobulle": "#E4E7EA", "desactive": "#6E757D", "clair": "#3A3F45",
            "moyen": "#2A2E33", "sombre": "#15171A",
        },
        "cadre": "#3A3F45", "fond_groupe": "#24272B", "entete": "#2C3035", "survol": "#2E3530",
        "bouton_fond": "#2F3338", "bouton_bord": "#474D54", "gris": "#9AA3AD",
    },
}


def feuille(t: dict) -> str:
    return f"""
QPushButton {{ padding: 6px 14px; border: 1px solid {t['bouton_bord']}; border-radius: 5px; background: {t['bouton_fond']}; }}
QPushButton:hover {{ border-color: {t['olive']}; }}
QPushButton:disabled {{ color: {t['couleurs']['desactive']}; }}
QPushButton[role="principal"] {{ background: {t['olive']}; color: white; border-color: {t['olive_fonce']}; font-weight: 600; }}
QPushButton[role="principal"]:hover {{ background: {t['olive_fonce']}; }}
QLabel[role="titre"] {{ font-size: 17pt; font-weight: 700; color: {t['olive']}; }}
QLabel[role="sous-titre"] {{ color: {t['gris']}; font-size: 10.5pt; }}
QGroupBox {{ font-weight: 600; border: 1px solid {t['cadre']}; border-radius: 8px; margin-top: 12px; padding-top: 10px; background: {t['fond_groupe']}; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; color: {t['olive']}; }}
QTableWidget {{ gridline-color: {t['cadre']}; border: 1px solid {t['cadre']}; }}
QHeaderView::section {{ background: {t['entete']}; padding: 5px; border: none; border-bottom: 1px solid {t['cadre']}; font-weight: 600; }}
QMenu {{ background: {t['couleurs']['base']}; border: 1px solid {t['cadre']}; padding: 4px; }}
QMenu::item {{ padding: 6px 26px 6px 10px; border-radius: 4px; }}
QMenu::item:selected {{ background: {t['olive']}; color: white; }}
QMenu::item:disabled {{ color: {t['gris']}; }}
QMenu::separator {{ height: 1px; background: {t['cadre']}; margin: 4px 6px; }}
QMenu::icon {{ padding-left: 6px; }}
"""


def theme(nom: str) -> dict:
    return THEMES.get(nom) or THEMES["sombre"]


def appliquer(app, nom: str = "sombre") -> None:
    import interface_kit
    t = theme(nom)
    interface_kit.appliquer_style(app, t["couleurs"], polices=POLICES, famille="Source Sans 3",
                                  taille=10.0, feuille=feuille(t), sombre=(nom == "sombre"))
