"""Sonde : un périphérique éjecté (code 47) peut-il revenir sans débrancher, et comment ?

    python outils/sonde_remontage.py "USB\\VID_xxxx&PID_yyyy\\INSTANCE"          (lecture seule)
    python outils/sonde_remontage.py "USB\\VID_xxxx&PID_yyyy\\INSTANCE" --essayer

Essaie, dans l'ordre, des méthodes SANS droits d'administrateur, et s'arrête à la
première qui ramène le périphérique ; affiche l'état (problème) avant et après chaque
essai. Rien n'est désinstallé.
"""
import ctypes
import sys
import time
from ctypes import wintypes

cfg = ctypes.WinDLL("cfgmgr32")
CR_SUCCESS = 0
CM_LOCATE_DEVNODE_PHANTOM = 0x1
CM_REENUMERATE_SYNCHRONOUS, CM_REENUMERATE_RETRY_INSTALLATION = 0x1, 0x2
CM_SETUP_DEVNODE_READY, CM_SETUP_DEVNODE_RESET = 0x0, 0x4
DN_STARTED, DN_HAS_PROBLEM = 0x8, 0x400


def localiser(ident):
    d = wintypes.DWORD()
    for drapeau in (0, CM_LOCATE_DEVNODE_PHANTOM):
        r = cfg.CM_Locate_DevNodeW(ctypes.byref(d), ident, drapeau)
        if r == CR_SUCCESS:
            return d.value, drapeau
    return None, r


def etat(dn):
    st, pb = wintypes.ULONG(), wintypes.ULONG()
    r = cfg.CM_Get_DevNode_Status(ctypes.byref(st), ctypes.byref(pb), dn, 0)
    return r, st.value, pb.value


def ident(dn):
    t = ctypes.create_unicode_buffer(512)
    cfg.CM_Get_Device_IDW(dn, t, 512, 0)
    return t.value


def parent(dn):
    p = wintypes.DWORD()
    return p.value if cfg.CM_Get_Parent(ctypes.byref(p), dn, 0) == CR_SUCCESS else None


def montrer(titre, dn):
    r, st, pb = etat(dn)
    print(f"  {titre}: CR={r} status=0x{st:X} demarre={bool(st & DN_STARTED)} "
          f"probleme={pb if st & DN_HAS_PROBLEM else 0}  [{ident(dn)}]")
    return pb if st & DN_HAS_PROBLEM else 0


def revenu(ident_dev):
    dn, _ = localiser(ident_dev)
    if dn is None:
        return False
    r, st, pb = etat(dn)
    return r == CR_SUCCESS and bool(st & DN_STARTED) and not (st & DN_HAS_PROBLEM)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    cible = sys.argv[1]
    essayer = "--essayer" in sys.argv
    print("admin =", bool(ctypes.windll.shell32.IsUserAnAdmin()))
    dn, drapeau = localiser(cible)
    if dn is None:
        print("introuvable (CR=%s) : débranché ou déjà rebranché ailleurs ?" % drapeau)
        return 1
    print("trouvé", "(fantôme)" if drapeau else "(présent)")
    montrer("périphérique", dn)
    p = parent(dn)
    if p is not None:
        montrer("parent", p)
    if not essayer:
        return 0
    essais = [
        ("CM_Reenumerate_DevNode(parent, SYNCHRONOUS)", lambda: cfg.CM_Reenumerate_DevNode(p, CM_REENUMERATE_SYNCHRONOUS)),
        ("CM_Setup_DevNode(dev, READY)", lambda: cfg.CM_Setup_DevNode(dn, CM_SETUP_DEVNODE_READY)),
        ("CM_Reenumerate_DevNode(dev, RETRY_INSTALLATION|SYNC)",
         lambda: cfg.CM_Reenumerate_DevNode(dn, CM_REENUMERATE_RETRY_INSTALLATION | CM_REENUMERATE_SYNCHRONOUS)),
        ("CM_Setup_DevNode(dev, RESET)", lambda: cfg.CM_Setup_DevNode(dn, CM_SETUP_DEVNODE_RESET)),
        ("CM_Reenumerate_DevNode(parent, RETRY_INSTALLATION|SYNC)",
         lambda: cfg.CM_Reenumerate_DevNode(p, CM_REENUMERATE_RETRY_INSTALLATION | CM_REENUMERATE_SYNCHRONOUS)),
    ]
    for nom, appel in essais:
        r = appel()
        time.sleep(3)
        ok = revenu(cible)
        print(f"essai {nom}: CR={r} -> {'REVENU' if ok else 'toujours absent'}")
        montrer("  après", localiser(cible)[0] or dn)
        if ok:
            print("METHODE QUI MARCHE :", nom)
            return 0
    print("aucune méthode sans droits d'administrateur n'a marché")
    return 2


if __name__ == "__main__":
    sys.exit(main())
