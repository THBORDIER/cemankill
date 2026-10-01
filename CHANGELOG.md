# Changelog

## 0.3.0 - 2026-10-01

Ajout d'un second pilote pour `https://cemanty.fr/jouer/`.

- Nouveau paquet `browser_bot/`, lance avec `python -m browser_bot`, sans Android ni `adb`.
- Reutilisation du solveur et des embeddings existants ; profil invite et observations web persistants.
- Passage automatique du tutoriel, detection du vrai champ Compose/Flutter et lecture du score via la couche semantique.
- Garde-fou strict : seules les URL HTTPS de `cemanty.fr` sont autorisees ; la session dediee est fermee en sortie.
- Mode `--check` pour valider le plateau sans envoyer de mot ; Edge installe est utilise par defaut.
- Validation reelle le 01/10/2026 : `maison` (-6,28), puis `animal` (0,02), lus et persistes par le pilote.
- Detection explicite de la limite du mode invite observee apres 29 essais ; aucun contournement par profils jetables.
- Soumission web au clavier sans clic sur la fleche, URL bornee a `/jouer/`, arret sur marqueur publicitaire ou iframe.
- Prise en charge du mot bonus gratuit avec `--all-sessions`, sans archive, duel, jeton ni publicite.
- Mode `--watch` : veille sans clic sur le compte a rebours, puis lancement autonome du prochain plateau.
- Lanceur Windows avec raccourci Bureau et icone de zone de notification pour demarrer, arreter et suivre le bot.
- Le menu d'affichage utilise le profil Edge Playwright connecte du bot, jamais le navigateur Windows par defaut.
- Mode `--archives` : selection des jours `A jouer`, acquisition bornee des jetons recompenses et enchainement
  automatique ; aucune interaction avec le contenu publicitaire et fermeture des seules commandes nommees.
- Validation reelle sur compte le 01/10/2026 : mot quotidien `perdant` en 29 essais et bonus `photosynthèse` en 26.
- Débrief factuel de la session dans `docs/DEBRIEF-2026-10-01.md`, avec distinction entre parcours validés et
  archives bloquées faute de jeton/publicité disponible.
- 75 tests unitaires passent.

## 0.2.1 - 2026-09-30

Durcissement de la securite de pilotage (travail de Codex, relu et teste).

- Detection fiable de l'appli au premier plan (`dumpsys activity`, repli sur `dumpsys window`) : `foreground_package()`.
- `ensure_app()` ne relance plus Cemanty : BACK immediat, verification toutes les 0,25 s ; echec ou premier plan
  inconnu => `SafetyAbort` et arret propre (`!! arret de securite`), plutot que d'agir a l'aveugle.
- Apres chaque tap sur la croix d'une pub, contrôle immediat du premier plan.
- 56 tests (dont 4 sur la lecture du premier plan : Play Store, repli sur la fenetre, sortie illisible).

## 0.2.0 - 2026-09-30

Refactoring en paquet Python et tests unitaires.

- Code decoupe en modules (`config`, `device`, `screen`, `solver`, `text`, `storage`, `game`, `navigation`, `cli`) ;
  seul `device.py` depend d'adb. Lancement : `python -m cemankill`.
- 42 tests unitaires (pytest) avec faux appareils : boucle de jeu, mots refuses, succes derriere le clavier, pub apres
  victoire, navigation avec et sans jeton, solveur sur monde synthetique (cibles retrouvees malgre un modele different).
- Corrige : apres une victoire en archive le bot cherchait le bouton « Terminer » alors que l'ecran propose « Fermer » ;
  il restait sur la fenetre de victoire et ne pouvait plus ouvrir le jour suivant. `leave_game()` gere les deux boutons,
  et la navigation ferme d'elle-meme une fenetre de victoire qui cache l'onglet Historique.
- Corrige : une pub dont la croix a ete mal touchee peut ouvrir Chrome ; `ensure_app()` quitte aussitot la page externe
  (BACK) ; si elle ne se ferme pas, ou si le premier plan est inconnu, le bot s'arrete (`SafetyAbort`) sans jamais
  interagir avec l'autre appli.
- Corrige : apres la pub recompensee le jeton est credite avec un delai (« Ton jeton arrive… ») ; `claim_token()` touche
  « Verifier » jusqu'a ce que « Jouer ce mot » reapparaisse.
- Corrige : une fenetre restee ouverte (victoire, jeton) cachait les onglets ; `go_to_history()` la ferme, avec retries.
- Corrige : balayage de liste deterministe (retour en haut puis pas lents), plus de jour saute par inertie.
- Non valide de bout en bout au moment de la publication : deux jours consecutifs d'affilee apres ces correctifs.
- Corrige (trouve par un test) : si l'ecran ne donnait jamais de score, le bot epuisait ses mots d'amorce puis
  plantait avec une exception ; il s'arrete maintenant en expliquant pourquoi.

## 0.1.0 - 2026-09-30

Premiere version, construite et validee le meme jour sur un emulateur Android 14 (Pixel 7).

- Pilotage de l'emulateur par `adb` : saisie (`input text`), lecture de l'ecran en texte (`uiautomator dump`).
- Embeddings bge-m3 (Ollama) de 40 000 mots francais ; solveur par regression a noyau sur vecteurs centres.
- Fermeture automatique des pubs plein ecran et des pubs recompensees (croix en haut a droite, detection du texte `Test Ad`).
- Fermeture automatique des succes debloques (le bouton Continuer est sous le clavier : on masque le clavier d'abord).
- Detection des mots refuses (champ non vide apres envoi) : on vide le champ et on ecarte le mot.
- Filtre des formes voisines (pluriel, feminin) : le jeu leur donne le meme score que la forme deja essayee.
- Enchainement des archives : jeton -> pub -> partie -> jour suivant.
- Persistance de tous les scores observes dans `data/obs.json`.

Corrige pendant la session (voir JOURNAL.md) :
- les mots refuses s'accolaient aux suivants dans le champ de saisie ;
- le bot tournait en rond sur des mots eloignes (evaluation mot par mot, vecteurs non centres) ;
- le bot restait bloque apres la victoire (fin de partie non detectee quand une pub s'affichait).
