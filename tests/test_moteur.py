"""Moteur de Pipit sur des périphériques imités : tri, regroupement, éjection, refus."""
import pytest

from pipit import bloqueurs, peripheriques, raccourci, reglages
from pipit.modele import Disque, regrouper, taille_lisible


def test_seuls_les_externes_sont_proposes():
    ids = [p.id for p in peripheriques.lister()]
    assert "USB\\VID_0781&PID_558C\\AA01" in ids
    assert not any("PCIIDE" in i for i in ids), "disque SATA interne proposé"
    assert len(ids) == 5                     # 3 clés/cartes, 1 SSD, 1 iPad


def test_disque_systeme_jamais_propose():
    d = Disque(0, "Clé", "USB", 1, ["C"], [""], "x", "USB\\VID_1&PID_2\\3", systeme=True)
    p = regrouper([d])[0]
    assert not peripheriques.visible(p, internes_a_chaud=True)


def test_internes_a_chaud_sur_demande():
    assert any("PCIIDE" in p.id for p in peripheriques.lister(internes_a_chaud=True))


def test_lecteur_multicarte_regroupe():
    lecteur = [p for p in peripheriques.lister() if p.id.startswith("USB\\VID_05E3")][0]
    assert lecteur.lecteur_de_cartes and lecteur.lettres == ["F"]
    assert len(lecteur.disques) == 2


def test_masquer_par_materiel():
    masques = {"USB\\VID_0951&PID_1666"}
    ids = [p.id for p in peripheriques.lister(masques)]
    assert not any("VID_0951" in i for i in ids)
    assert any("VID_0951" in p.id for p in peripheriques.lister(masques, avec_masques=True))


def test_materiel_sans_numero_d_instance():
    p = peripheriques.lister()[0]
    assert p.materiel == "USB\\VID_0781&PID_558C"


def test_ejection_reussie_retire_de_la_liste():
    p = [p for p in peripheriques.lister() if "VID_0951" in p.id][0]
    assert peripheriques.ejecter(p).ok
    assert not any("VID_0951" in q.id for q in peripheriques.lister())


def test_refus_donne_le_programme(monkeypatch):
    monkeypatch.setenv("PIPIT_DEMO_REFUS", "1")
    monkeypatch.setattr(peripheriques.time, "sleep", lambda s: None)
    r = peripheriques.ejecter(peripheriques.lister()[0])
    assert not r.ok and r.veto == peripheriques.VETO_FICHIER_OUVERT
    assert r.bloqueurs and r.bloqueurs[0].programme == "WINWORD.EXE" and r.bloqueurs[0].fermable


def test_aucun_peripherique(monkeypatch):
    monkeypatch.setenv("PIPIT_DEMO_VIDE", "1")
    assert peripheriques.lister() == []


@pytest.mark.parametrize("octets,fr,en", [(0, "", ""), (954_000_000_000, "954 Go", "954 GB"),
                                          (63_864_569_856, "63,9 Go", "63.9 GB"), (3_726_000_000_000, "3,7 To", "3.7 TB")])
def test_taille_lisible(octets, fr, en):
    assert taille_lisible(octets, "fr") == fr and taille_lisible(octets, "en") == en


@pytest.mark.parametrize("texte,attendu", [
    ("Win+Alt", (0x8, 0x12)),                # réglage repris d'USB Safely Remove
    ("Ctrl+Alt+E", (0x3, ord("E"))),
    ("Win+Shift+F12", (0xC, 0x7B)),
    ("Ctrl+Alt+Shift+E", (0x7, ord("E"))),
    ("", None), ("E", None), ("Alt", None), ("Ctrl+Truc", None),
])
def test_raccourcis(texte, attendu):
    assert raccourci.analyser(texte) == attendu


def test_choix_proposes_tous_valides():
    for t in raccourci.CHOIX_MENU + raccourci.CHOIX_TOUT:
        assert t == "" or raccourci.analyser(t), t


def test_journal_225_lu_quels_que_soient_les_champs():
    evs = [{"donnees": {"ProcessId": "1234", "ProcessName": "\\Device\\HarddiskVolume3\\Windows\\explorer.exe",
                        "DeviceInstance": "USB\\VID_0951"}},
           {"donnees": {"Param1": "\\Device\\HarddiskVolume3\\Tools\\vlc.exe", "Param2": "5678"}}]
    bs = bloqueurs.analyser(evs)
    assert [(b.pid, b.programme) for b in bs] == [(1234, "explorer.exe"), (5678, "vlc.exe")]
    assert bs[0].explorateur and not bs[0].fermable
    assert bs[1].fermable


def test_antivirus_jamais_ferme():
    b = bloqueurs.Bloqueur(900, "MsMpEng.exe")
    assert b.patienter and not b.fermable and not bloqueurs.fermer(b)


def test_reglages_aller_retour():
    r = reglages.charger()
    assert r.raccourci_menu == "Win+Alt"
    r.masques = ["USB\\VID_0951&PID_1666"]
    r.noms = {"USB\\VID_0781&PID_558C": "Sauvegarde photo"}
    reglages.enregistrer(r)
    r2 = reglages.charger()
    assert r2.masques == r.masques and r2.noms == r.noms


def test_reglages_abimes_ne_cassent_rien(donnees):
    donnees.mkdir(parents=True, exist_ok=True)
    (donnees / "reglages.json").write_text("{pas du json", encoding="utf-8")
    assert reglages.charger().raccourci_menu == "Win+Alt"


def test_suffixes_de_windows_retires():
    from pipit.modele import nettoyer_nom
    assert nettoyer_nom("Micron CT4000X6SSD9 SCSI Disk Device") == "Micron CT4000X6SSD9"
    assert nettoyer_nom("SanDisk Extreme Pro USB Device") == "SanDisk Extreme Pro"
    assert nettoyer_nom("Kingston DataTraveler 3.0") == "Kingston DataTraveler 3.0"



# ------------------------------------------------------------ 0.2.0
def test_types_devines():
    types = {p.nom: p.type for p in peripheriques.lister()}
    assert types["Kingston DataTraveler 3.0"] == "cle"
    assert types["Generic STORAGE DEVICE"] == "carte"
    assert types["Samsung Portable SSD T7"] == "ssd"
    assert types["Apple iPad"] == "tablette"


@pytest.mark.parametrize("nom,attendu,options", [
    ("AV PRO C Fexpress SE", "carte", {}), ("Micron CT4000X6SSD9", "ssd", {}),
    ("WD Elements 25A2", "hdd", {"ssd": False}), ("ST4000DM004", "interne", {"bus": "SATA"}),
    ("NIKON Z 8", "photo", {"appareil": "telephone"}), ("Pixel 8", "telephone", {"appareil": "telephone"}),
    ("HL-DT-ST DVDRAM", "optique", {"appareil": "optique"}),
])
def test_types_reels(nom, attendu, options):
    from pipit.modele import deviner_type
    bus = options.pop("bus", "USB")
    assert deviner_type([Disque(1, nom, bus, **options)]) == attendu


def test_appareils_masquables_par_option():
    assert not any(p.type == "tablette" for p in peripheriques.lister(appareils=False))


def test_remontage():
    p = [p for p in peripheriques.lister() if "VID_0951" in p.id][0]
    assert peripheriques.ejecter(p).ok
    attente = peripheriques.en_attente_de_retrait()
    assert [i for i, _n in attente] == [p.id]
    assert peripheriques.remonter(p.id)["ok"]
    assert peripheriques.en_attente_de_retrait() == []
    assert any("VID_0951" in q.id for q in peripheriques.lister())


def test_forcer():
    p = peripheriques.lister()[0]
    assert peripheriques.forcer(p)["ok"]
    assert p.id not in [q.id for q in peripheriques.lister()]


def test_coupables():
    p = peripheriques.lister()[0]
    sans = peripheriques.coupables(p)
    partout = peripheriques.coupables(p, partout=True)
    assert sans[0].programme == "WINWORD.EXE" and partout[0].fichiers == ["E:\\Rapport.docx"]


def test_assistant_refuse_les_demandes_douteuses():
    from pipit import assistant
    assert not assistant.demander("formater", "USB\\VID_1")["ok"]
    assert not assistant.demander("forcer", "C:\\Windows & del")["ok"]
    assert assistant._traiter({"action": "rm", "id": "USB\\X"})["detail"] == "demande invalide"


def test_assistant_tache_xml():
    from pipit import assistant
    xml = assistant.xml_tache()
    assert "HighestAvailable" in xml and "--assistant" in xml and "<Triggers>" not in xml


def test_assistant_traite_ses_fichiers(donnees):
    import json
    from pipit import assistant
    d = assistant.dossier() / "demande-essai.json"
    d.write_text(json.dumps({"action": "coupables", "id": "USB\\VID_0781&PID_558C\\AA01", "lettres": ["E"]}),
                 encoding="utf-8")
    assert assistant.executer() == 0
    r = json.loads((assistant.dossier() / "reponse-essai.json").read_text(encoding="utf-8"))
    assert r["ok"] and r["coupables"][0]["programme"] == "WINWORD.EXE"
