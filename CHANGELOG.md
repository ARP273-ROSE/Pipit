# Journal des versions — Pipit

### 0.3.0

Sécurité (audit complet) :
- 🔴 Plus de tâche planifiée « Pipit\Assistant » : elle lançait avec les droits d'administrateur des
  fichiers modifiables par n'importe quel programme de la session (contournement de l'UAC). Chaque geste
  administrateur passe désormais par la fenêtre UAC ; l'ancienne tâche est détectée et retirée.
- Échange avec le processus élevé par un canal nommé aléatoire, authentifié par une clé à usage unique
  (plus aucun fichier écrit ou effacé avec les droits d'administrateur dans le profil).
- Le processus élevé recalcule lui-même le périphérique et ses lettres (ignore ce qu'on lui envoie),
  refuse les disques internes et le disque système ; « remonter » n'agit que sur un périphérique éjecté
  encore branché (problème 47), jamais sur un périphérique désactivé exprès.
- Plus aucune fermeture de fichiers dans un autre programme (action supprimée).

Gels, plantages, performance :
- Liste des périphériques lue en arrière-plan, relue au branchement (WM_DEVICECHANGE) ; sondage de
  secours toutes les 10 s au lieu de 2,5 s ; aucune lecture pendant une éjection.
- Icône redessinée seulement quand le nombre change ; double clic = un seul menu.
- Éjection forcée : volumes gardés verrouillés jusqu'à l'éjection.
- Recherche des fichiers ouverts : un seul inventaire, une seule recherche à la fois.
- Journal de Windows : seuls les événements de CE périphérique, plus de numéro de programme deviné.
- Fin de session : éjection rapide, sans recherche de coupables.
- Boîte « insérez un disque » coupée pour le seul fil de lecture ; clé « Run » créée si absente.

Nouveautés :
- Lecteurs CD/DVD (internes compris) : un clic ouvre le tiroir ; « Fermer le tiroir ».
- Images ISO et disques VHD montés : un clic les démonte.
- « Montrer » : met au premier plan le programme qui bloque.

### 0.2.0

- Éjection forcée : caches vidés, volume démonté même avec des fichiers ouverts, puis éjection
  (confirmation à chaque fois ; un document non enregistré est perdu).
- Remontage sans débrancher d'un périphérique éjecté (problème 47), qu'il l'ait été par Pipit,
  par Windows ou par un autre outil.
- Assistant administrateur : tâche planifiée créée une fois (une seule fenêtre UAC) pour le
  remontage, l'éjection forcée et la recherche complète ; sans elle, une fenêtre UAC par geste.
- Qui bloque : inventaire des fichiers ouverts (programme + chemin), en plus du journal de Windows ;
  « Chercher partout » voit aussi les programmes de Windows et l'antivirus.
- Types reconnus : clé, carte mémoire, SSD, disque dur, disque interne, lecteur CD/DVD,
  téléphone, tablette, appareil photo ; icône par type, type corrigeable, icône personnalisée.
- Téléphones, tablettes et appareils photo dans le menu (option).
- Thème sombre (par défaut) ou clair, au choix.
- Icône : nombre de périphériques, grisée quand il n'y a rien à retirer.
- Clic gauche = menu d'éjection, clic droit = menu complet (forcer, qui bloque, ouvrir, réglages).
- Rappel des périphériques oubliés à la fermeture de session (option).

### 0.1.0

Première version.

- Icône près de l'horloge : clic → liste des clés, disques et cartes à retirer ; un clic éjecte.
- Raccourcis clavier globaux : menu (Win+Alt par défaut), tout éjecter (aucun par défaut).
- Quand Windows refuse : le programme en cause est nommé (journal Kernel-PnP, événement 225),
  avec un bouton pour le fermer proprement ; antivirus, indexation et Explorateur jamais fermés.
- Lecteurs multicartes regroupés ; question avant de retirer tout le lecteur.
- Disques SATA « branchés à chaud » et disque de Windows jamais proposés par défaut.
- Noms personnalisés et périphériques masqués, retenus par identifiant matériel (VID/PID).
- Lancement avec Windows (HKCU\…\Run), sans droits d'administrateur.
- Ligne de commande : `--lister`, `--ejecter E`.
- Kit commun : installeur, mises à jour signées, rapports d'incident, français et anglais.
