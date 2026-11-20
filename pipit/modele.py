"""Ce que Pipit sait d'un disque, indépendamment du système (testable partout)."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Disque:
    numero: int
    nom: str
    bus: str
    taille: int = 0
    lettres: list[str] = field(default_factory=list)
    volumes: list[str] = field(default_factory=list)       # noms de volume, même ordre que lettres
    id_disque: str = ""
    id_ejectable: str = ""     # nœud qu'on éjecte (boîtier USB…) ; vide = pas éjectable
    id_parent: str = ""        # parent de ce nœud (le port / le concentrateur)
    support_amovible: bool = False   # carte SD, clé : le support se retire du lecteur
    systeme: bool = False


@dataclass
class Peripherique:
    """Un objet que l'on débranche : un ou plusieurs disques derrière le même nœud éjectable
    (lecteur multicarte, boîtier à plusieurs disques)."""
    id: str
    disques: list[Disque]

    @property
    def lettres(self) -> list[str]:
        return [l for d in self.disques for l in d.lettres]

    @property
    def nom(self) -> str:
        noms = []
        for d in self.disques:
            if d.nom not in noms:
                noms.append(d.nom)
        if len(noms) > 1:
            # lecteur multicarte : « Generic STORAGE DEVICE (SD) », « … (CF) » → partie commune
            import os.path
            commun = os.path.commonprefix(noms).rstrip(" (-_")
            if len(commun) >= 4:
                return commun
        return " + ".join(noms)

    @property
    def taille(self) -> int:
        return sum(d.taille for d in self.disques)

    @property
    def bus(self) -> str:
        return self.disques[0].bus if self.disques else "?"

    @property
    def materiel(self) -> str:
        """Identifiant matériel stable (USB\\VID_xxxx&PID_yyyy), sans le numéro d'instance :
        c'est lui qu'on retient pour masquer ou renommer un périphérique."""
        morceaux = self.id.split("\\")
        return "\\".join(morceaux[:2]).upper() if len(morceaux) >= 2 else self.id.upper()

    @property
    def lecteur_de_cartes(self) -> bool:
        """Plusieurs fentes derrière un même boîtier : éjecter une carte retire TOUT le
        lecteur (Windows ne sait pas faire autrement), d'où la question posée avant."""
        return len(self.disques) > 1


def regrouper(disques: list[Disque]) -> list[Peripherique]:
    groupes: dict[str, list[Disque]] = {}
    for d in disques:
        if d.id_ejectable:
            groupes.setdefault(d.id_ejectable, []).append(d)
    perifs = [Peripherique(i, sorted(ds, key=lambda d: (d.lettres or ["~"])[0])) for i, ds in groupes.items()]
    return sorted(perifs, key=lambda p: ((p.lettres or ["~"])[0], p.nom))


def taille_lisible(octets: int, langue: str = "fr") -> str:
    if octets <= 0:
        return ""
    unites = ["o", "Ko", "Mo", "Go", "To"] if langue == "fr" else ["B", "KB", "MB", "GB", "TB"]
    x, i = float(octets), 0
    while x >= 1000 and i < len(unites) - 1:
        x, i = x / 1000, i + 1
    texte = f"{x:.0f}" if x >= 100 or i == 0 else f"{x:.1f}"
    if langue == "fr":
        texte = texte.replace(".", ",")
    return f"{texte} {unites[i]}"
