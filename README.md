# Pipit

**Français** · [English](#english)

Retirer une clé USB, un disque externe ou une carte mémoire sans risque, depuis
l'icône près de l'horloge de Windows. Logiciel libre et gratuit.

- **Un clic** sur l'icône : la liste de ce qui peut être retiré (lettre, nom, taille).
  Un clic sur une ligne l'éjecte, et Pipit prévient quand on peut débrancher.
- **Un raccourci clavier**, actif partout : Win+Alt ouvre le menu (modifiable),
  un second raccourci peut tout éjecter d'un coup.
- **Quand Windows refuse**, Pipit dit quel programme garde un fichier ouvert et
  propose de le fermer proprement (jamais de fermeture forcée ; l'Explorateur,
  l'antivirus et l'indexation ne sont jamais fermés).
- Disque de Windows et disques internes **jamais proposés** par défaut.
- Noms personnalisés, périphériques masqués, lecteurs multicartes regroupés.
- Aucun droit d'administrateur, aucun pilote, aucun service : Pipit utilise les
  mêmes fonctions de Windows que l'icône « Retirer le périphérique en toute sécurité ».

## Installation

Télécharger `Pipit-Setup.exe` dans la
[dernière version](https://github.com/ARP273-ROSE/Pipit/releases/latest), puis
le lancer (installation pour l'utilisateur, sans fenêtre d'administrateur).
Pipit se met ensuite à jour tout seul : chaque mise à jour est signée et vérifiée
avant d'être installée.

## Ligne de commande

```
python run.py --lister        périphériques retirables, sans rien éjecter
python run.py --ejecter E     éjecte le périphérique qui porte la lettre E:
```

Manuel complet : menu de l'icône → *Manuel (PDF)*.

---

## English

Safely remove a USB stick, an external drive or a memory card from the icon next
to the Windows clock. Free and open-source software.

- **One click** on the icon lists what can be removed (letter, name, size). One
  click on a line ejects it, and Pipit tells you when it is safe to unplug.
- **A global keyboard shortcut**: Win+Alt opens the menu (configurable); a second
  shortcut can eject everything at once.
- **When Windows refuses**, Pipit names the program that keeps a file open and
  offers to close it politely (never forced; File Explorer, the antivirus and
  indexing are never closed).
- The Windows disk and internal disks are **never offered** by default.
- Custom names, hidden devices, multi-card readers grouped together.
- No administrator rights, no driver, no service: Pipit uses the same Windows
  functions as the “Safely Remove Hardware” icon.

### Installation

Download `Pipit-Setup.exe` from the
[latest release](https://github.com/ARP273-ROSE/Pipit/releases/latest) and run
it (per-user install, no administrator prompt). Pipit then updates itself; every
update is signed and verified before it is installed.

### Command line

```
python run.py --list          removable devices, nothing is ejected
python run.py --eject E       ejects the device holding drive E:
```

Full guide: icon menu → *User guide (PDF)*.

Licence MIT.
