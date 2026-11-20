# Pipit — progression

Remplaçant libre d'un utilitaire payant d'éjection USB : icône près de l'horloge,
éjection par CM_Request_Device_EjectW, programme fautif lu dans le journal
Kernel-PnP (événement 225), raccourcis globaux RegisterHotKey.

## État

- 0.1.0 publiée le 20/11/2026 (Setup 43 Mo, archive de MAJ signée). Éjection réelle réussie sur un vrai poste (disque USB CFexpress, code 0, volume disparu).

- 0.2.0 publiée le 20/11/2026 (assistant par tâche planifiée : REMPLACÉ en 0.3.0, voir plus bas) : coupables par inventaire des poignées, types + icônes,
  thème clair/sombre, compteur sur l'icône, rappel à la fermeture de session.
  - Mesuré sur un vrai poste : sans droits d'administrateur, toutes les fonctions de remontage
    (CM_Setup_DevNode, CM_Reenumerate_DevNode) répondent CR_ACCESS_DENIED (51).
  - CI windows-latest : création réelle de la tâche, poignées (un sous-processus qui garde un
    fichier ouvert est trouvé), en 0,1 s.
  - NON vérifié sur un vrai poste : remontage en administrateur (quelle méthode de
    `admin_windows.remonter` marche), éjection forcée, téléphones/appareils photo.

- 0.3.0 publiée le 20/11/2026 après audit + contre-audit de sécurité par un agent : la tâche planifiée
  de la 0.2.0 était un contournement de l'UAC (code modifiable par l'utilisateur lancé avec les droits
  élevés) → supprimée (cherchée et retirée au démarrage) ; chaque geste admin = une UAC ; canal nommé
  aléatoire + clé + pid vérifié aux deux bouts, JSON ; le processus élevé recalcule le périphérique.
  Anti-gel : lecture en fil + WM_DEVICECHANGE. Tiroir CD/DVD (IOCTL_STORAGE_EJECT_MEDIA), démontage
  ISO/VHD (verbe Eject du Shell, puis Dismount-DiskImage) vérifié en CI sur un vrai VHD.

## Points d'architecture

- `pipit/disques_windows.py` : SetupAPI (GUID_DEVINTERFACE_DISK) → numéro de disque,
  bus (IOCTL_STORAGE_QUERY_PROPERTY), taille (GEOMETRY_EX), lettres (\\.\X: →
  numéro), ancêtre amovible (CM_DEVCAP_REMOVABLE) = nœud éjecté. Accès 0 : pas d'UAC.
- `pipit/peripheriques.py` : tri (bus USB/SD/MMC/1394 seulement, disque système exclu,
  SATA « à chaud » sur option), regroupement par nœud éjectable, 2 essais.
- `pipit/bloqueurs.py` : événement 225 lu par PowerShell Get-WinEvent ; jamais de
  fermeture forcée ; Explorateur, antivirus, indexation jamais fermés.
- Masquage et noms par identifiant matériel `USB\VID_xxxx&PID_yyyy` (sans instance).
- `PIPIT_DEMO=1` : périphériques imités (tests, captures du manuel).

## Reste à faire

- ✅ 20/11 : détection vérifiée sur un vrai poste (2 disques USB vus, SATA/NVMe/système/virtuel exclus).
- Reste : essai d'un refus réel (programme fautif nommé), d'un lecteur multicarte, de l'appli complète (icône, Win+Alt à la frappe) installée.
- ✅ CI windows-latest : RegisterHotKey accepte Win+Alt (MOD_WIN + VK_MENU). Reste à vérifier qu'il se déclenche à la frappe sur un vrai poste.
- L'entrée « Run » n'est pas retirée par la désinstallation (gabarit commun de l'installeur).
