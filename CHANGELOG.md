# Changelog

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
