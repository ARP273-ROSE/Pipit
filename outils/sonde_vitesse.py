"""Sonde en LECTURE SEULE : durée de la liste et lecture brute des vitesses USB.

    python outils/sonde_vitesse.py

N'éjecte rien, n'écrit rien, sans droits d'administrateur.
"""
import os
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipit import disques_windows as dw, usb  # noqa: E402

for essai in (1, 2, 3):
    t = time.perf_counter()
    disques = dw.lister()
    print(f"lister n°{essai} : {time.perf_counter() - t:.2f} s")
    for d in disques:
        print(f"   disque {d.numero} {d.nom} taille={d.taille} vitesse={d.vitesse}/{d.vitesse_max}")

t = time.perf_counter()
dw._disques_physiques()
print(f"_disques_physiques seul : {time.perf_counter() - t:.2f} s")
t = time.perf_counter()
dw._lettres_par_disque()
print(f"_lettres_par_disque seul : {time.perf_counter() - t:.2f} s")

for d in dw.lister():
    if not d.id_ejectable.upper().startswith("USB\\"):
        continue
    print(d.id_ejectable)
    t = time.perf_counter()
    hp = usb._hub_et_port(d.id_ejectable)
    print(f"   hub/port {hp} ({time.perf_counter() - t:.2f} s)")
    if not hp:
        continue
    h = usb._ouvrir_hub(hp[0], False)
    print(f"   hub ouvert : {bool(h)}")
    if h:
        r = dw._ioctl(h, usb.IOCTL_USB_GET_NODE_CONNECTION_INFORMATION_EX, struct.pack("<I", hp[1]) + bytes(508), 512)
        print(f"   EX : speed={r[23] if r else None} bcdUSB={hex(struct.unpack_from('<H', r, 6)[0]) if r else None}")
        v2 = dw._ioctl(h, usb.IOCTL_USB_GET_NODE_CONNECTION_INFORMATION_EX_V2,
                       struct.pack("<IIII", hp[1], 16, 0x7, 0), 16)
        print(f"   V2 : {v2.hex() if v2 else None}")
        dw.kernel32.CloseHandle(h)
    t = time.perf_counter()
    usb._cache.clear()
    print(f"   vitesse = {usb.vitesse(d.id_ejectable)} ({time.perf_counter() - t:.2f} s)")
