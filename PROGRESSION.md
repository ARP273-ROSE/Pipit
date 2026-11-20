# Pipit — progression

Remplaçant libre d'un utilitaire payant d'éjection USB : icône près de l'horloge,
éjection par CM_Request_Device_EjectW, programme fautif lu dans le journal
Kernel-PnP (événement 225), raccourcis globaux RegisterHotKey.

## État

- 0.1.0 : première version (voir CHANGELOG.md).

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
- Essai réel d'éjection sur un vrai poste (clé, disque, lecteur multicarte).
- Vérifier sur un vrai poste que Win+Alt (touche de modification seule) déclenche bien.
- L'entrée « Run » n'est pas retirée par la désinstallation (gabarit commun de l'installeur).
