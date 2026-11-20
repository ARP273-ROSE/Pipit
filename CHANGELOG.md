# Journal des versions — Pipit

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
