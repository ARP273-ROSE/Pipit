"""Raccourcis clavier globaux (RegisterHotKey), actifs quelle que soit la fenêtre au premier plan.

Un raccourci s'écrit « Win+Alt », « Ctrl+Alt+E », « Win+Shift+F12 »… Quand il n'y a
que des touches de modification (« Win+Alt », le réglage d'USB Safely Remove), la
dernière sert de touche : Windows reçoit Alt pressée pendant que Win est tenue.
"""
from __future__ import annotations

import sys

MOD = {"ALT": 0x1, "CTRL": 0x2, "SHIFT": 0x4, "WIN": 0x8}
MOD_NOREPEAT = 0x4000
VK_MOD = {"ALT": 0x12, "CTRL": 0x11, "SHIFT": 0x10, "WIN": 0x5B}
WM_HOTKEY = 0x0312

CHOIX_MENU = ["", "Win+Alt", "Win+Alt+E", "Ctrl+Alt+E", "Ctrl+Shift+E", "Win+Shift+E", "Ctrl+Alt+U"]
CHOIX_TOUT = ["", "Ctrl+Alt+Shift+E", "Win+Alt+Shift+E", "Ctrl+Alt+Shift+U"]
CHOIX_APPAREIL = [""] + [f"Ctrl+Alt+{i}" for i in range(1, 10)] + [f"Win+Alt+{i}" for i in range(1, 10)]


def analyser(texte: str) -> tuple[int, int] | None:
    """(modificateurs, code de touche virtuelle) ou None si le texte est vide ou faux."""
    morceaux = [m.strip().upper() for m in (texte or "").split("+") if m.strip()]
    if not morceaux:
        return None
    mods, touche = 0, None
    for i, m in enumerate(morceaux):
        dernier = i == len(morceaux) - 1
        if m in MOD and not (dernier and mods and all(x in MOD for x in morceaux)):
            mods |= MOD[m]
        elif m in MOD:
            touche = VK_MOD[m]
        elif dernier and len(m) == 1 and m.isalnum():
            touche = ord(m)
        elif dernier and m.startswith("F") and m[1:].isdigit() and 1 <= int(m[1:]) <= 24:
            touche = 0x6F + int(m[1:])
        else:
            return None
    if touche is None or not mods:
        return None                    # une touche seule volerait la frappe normale
    return mods, touche


class Raccourcis:
    """Enregistre les raccourcis sur une fenêtre ; WM_HOTKEY arrive par le filtre natif de Qt."""

    def __init__(self, hwnd: int):
        self.hwnd = hwnd
        self.actions: dict[int, object] = {}
        self._suivant = 1

    def ajouter(self, texte: str, action) -> bool:
        cle = analyser(texte)
        if cle is None or sys.platform != "win32":
            return cle is not None
        import ctypes
        ident = self._suivant
        if not ctypes.windll.user32.RegisterHotKey(self.hwnd, ident, cle[0] | MOD_NOREPEAT, cle[1]):
            return False               # déjà pris par un autre programme
        self.actions[ident] = action
        self._suivant += 1
        return True

    def tout_retirer(self) -> None:
        if sys.platform == "win32":
            import ctypes
            for ident in self.actions:
                ctypes.windll.user32.UnregisterHotKey(self.hwnd, ident)
        self.actions.clear()

    def message(self, msg: int, wparam: int) -> bool:
        if msg == WM_HOTKEY and wparam in self.actions:
            self.actions[wparam]()
            return True
        return False
