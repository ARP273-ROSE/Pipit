# Journal des versions — Pipit

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
