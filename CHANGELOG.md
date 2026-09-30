# Changelog

## 0.2.0 - 2026-09-30

Refactoring en paquet Python et tests unitaires.

- Code decoupe en modules (`config`, `device`, `screen`, `solver`, `text`, `storage`, `game`, `navigation`, `cli`) ;
  seul `device.py` depend d'adb. Lancement : `python -m cemankill`.
- 42 tests unitaires (pytest) avec faux appareils : boucle de jeu, mots refuses, succes derriere le clavier, pub apres
  victoire, navigation avec et sans jeton, solveur sur monde synthetique (cibles retrouvees malgre un modele different).
- Corrige : apres une victoire en archive le bot cherchait le bouton « Terminer » alors que l'ecran propose « Fermer » ;
  il restait sur la fenetre de victoire et ne pouvait plus ouvrir le jour suivant. `leave_game()` gere les deux boutons,
  et la navigation ferme d'elle-meme une fenetre de victoire qui cache l'onglet Historique.
- Corrige : une pub dont la croix a ete mal touchee peut ouvrir Chrome ; `ensure_app()` ramene Cemanty au premier plan
  (BACK puis relance) sans jamais interagir avec l'autre appli.
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
