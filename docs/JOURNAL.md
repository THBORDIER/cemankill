# Journal de la session du 30/09/2026

Déroulé chronologique, erreurs comprises. Seuls les faits constatés sont notés ; ce qui n'a pas été vérifié est dit.

## 1. Mise en place de l'émulateur (~7 h 15)

- Aucun outil Android sur le poste, virtualisation active. Installation sans droits administrateur : JDK 17 portable
  (Temurin), outils en ligne de commande Android, `platform-tools`, `emulator`, image système
  `google_apis_playstore` API 34 x86_64. Création d'un Pixel 7.
- Le Play Store étant présent, le demandeur s'y est connecté et a installé l'appli. Aucun mot de passe n'a transité par
  l'assistant.

## 2. Exploration à la main (~7 h 22 – 7 h 40)

- Onboarding : deux mauvais taps m'ont envoyé sur l'écran « mot de passe oublié » puis « connexion » avant de retrouver
  l'appli. Leçon : **un tap à la fois, une lecture d'écran entre deux** tant que l'on ne connaît pas l'interface.
- Mot du jour déjà trouvé par le demandeur ; je n'y ai pas touché.
- **Mot bonus** : « album » trouvé en 31 essais avec une approche manuelle (mots-thèmes larges, puis champ lexical :
  musique 888/1000 → chanson 998/1000 → album 1000/1000).
- **Archives** : rejouer un jour passé coûte 1 jeton (0 au départ). Une pub récompensée en deux parties en donne un.
  Jour n° 28 : « hélicoptère », 33 essais (manuel).

## 3. Première automatisation, et ses erreurs

| Constat | Cause | Correctif |
|---|---|---|
| Les captures d'écran coûtent cher en tokens | Une image par lecture | `uiautomator dump` : lecture du texte de l'écran, pas d'image |
| Des mots s'accolaient (`pcultiverpousser…`) | Un mot refusé reste dans le champ ; le suivant s'y ajoute | Après chaque envoi, contrôle du champ ; s'il n'est pas vide, on le vide et on écarte le mot |
| `adb input text` plante sur `forêt` | `input text` est limité à l'ASCII | Saisie sans accents ; l'appli normalise |
| Message « Impossible de joindre le serveur » | Réseau OK (ping). Hypothèse : limitation de débit | Non résolu côté appli ; le bot attend et retente |
| Pub plein écran après une victoire | Annonce de test Google ; croix après 5-10 s | `close_ads()` : détecte `Test Ad`, touche la croix jusqu'à disparition |

## 4. Le solveur

1. **Version 1** (une régression linéaire par mot candidat, vecteurs non centrés) : le demandeur a constaté que le
   bot « boucle sur des trucs lointains ». Sur le jour n° 27, meilleur score après 100 essais : 40,68
   (`nutriments`, 937/1000), pour une cible qui était `toxine`.
2. **Version 2** (régression à noyau sur vecteurs centrés, tous les scores utilisés ensemble) : sur le même jour, le
   bot a enchaîné `parasite` (42,68), `infection`, `contamination`, puis trouvé la cible `toxine`, en une
   trentaine d'essais de sa propre série. Le jeu affiche 119 essais au total pour ce jour, les essais des deux
   versions s'additionnant ; la décomposition exacte n'a pas été relevée.
3. Constat utile : le jeu donne le **même score** au singulier et au pluriel (`animal`/`animaux`). Le bot écarte
   désormais les formes voisines d'un mot déjà essayé.

## 5. Les deux blocages qui ont vraiment coûté du temps

1. **Le succès « Marathonien »** (100ᵉ proposition). Sa fenêtre s'ouvre avec le clavier levé, qui recouvre ses
   boutons. Le bot tapait « Continuer » **sur le clavier** et restait bloqué. Correctif : masquer le clavier
   (`KEYCODE_BACK`), toucher « Continuer », redonner le focus au champ.
2. **La fin de partie non reconnue.** Après la victoire, une pub puis l'historique s'affichaient ; le bot attendait
   un écran « Tu as trouvé » qui ne venait pas et continuait à taper dans le vide, ce qui a ouvert par hasard la
   fenêtre des jetons. Correctif : on considère la partie terminée dès que l'on n'est plus sur l'écran de jeu
   (ni `Abandonner` ni champ de saisie) et qu'aucune pub ni aucun succès n'est affiché.

Retenu : **le solveur n'est pas le cœur du problème ; ce sont la navigation dans l'appli et le cycle pub → jeton → partie
qu'il faut fiabiliser** (remarque du demandeur, confirmée par les deux blocages ci-dessus).

## 6. Cycle pub → jeton → partie

Constaté sur le jour n° 26 : plus de jeton → « Regarder une pub » → pub en deux parties fermée automatiquement →
1 jeton reçu → « Jouer ce mot » → partie ouverte. Le cycle complet fonctionne de bout en bout.

## 7. Résultats de la série d'archives (robot, version 2)

| Jour | Mot | Essais du robot | Durée | Remarque |
|---|---|---|---|---|
| n° 27 (27/09) | toxine | ≈ 27 (119 au total avec la version 1) | non chronométré | première résolution par le solveur |
| n° 26 (26/09) | médicament | 58 | 283 s | premier jour joué de bout en bout par le robot, jeton et pub compris |
| n° 59 (25/09) | violence | 42 | 183 s | code refactoré, navigation depuis l'écran de victoire précédent comprise |
| n° 58 (24/09) | — | en cours | — | lancé quand le dépôt a été poussé ; résultat non relevé |

Cadence observée : environ 16 essais par minute. Le premier essai de bout en bout du code refactoré a résolu le n° 59. Les scores de tous les essais sont conservés dans `data/obs.json`
(non versionné). La série continue sur le jour suivant ; ce tableau est complété à la fin.

## 8. Enchaîner deux jours d'affilée : quatre pannes de navigation, toutes constatées en réel

Le solveur marche ; c'est le **passage d'un jour au suivant** qui a coûté le plus de temps. Chaque panne a été
constatée sur l'émulateur, puis corrigée et couverte par un test unitaire.

| # | Symptôme | Cause constatée | Correctif |
|---|---|---|---|
| 1 | « Impossible d'ouvrir la prochaine archive » après une victoire | En archive, l'écran de victoire a un bouton **Fermer** (le bot cherchait « Terminer », celui du mot bonus) ; la fenêtre cachait l'onglet Historique | `leave_game()` essaie Terminer, Fermer, Plus tard |
| 2 | Le jour n° 25 sauté | Un balayage rapide fait défiler une dizaine de jours par inertie | Retour en haut de liste, puis petits pas lents |
| 3 | L'appli disparaît, Chrome s'affiche | Un tap sur la croix d'une pub est tombé sur l'annonce et a ouvert la page de l'annonceur (Chrome, écran d'accueil). Rien n'a été saisi dans Chrome | `ensure_app()` : si une autre appli est au premier plan, BACK puis relance de Cemanty |
| 4 | « Ton jeton arrive… Réessaie dans un instant » | Le jeton est crédité avec un délai côté serveur ; un bouton **Vérifier** le valide | `claim_token()` touche Vérifier jusqu'à ce que « Jouer ce mot » réapparaisse |
| 5 | « Onglet Historique introuvable » au démarrage | Une fenêtre « Ce mot te coûte un jeton » restée ouverte d'un essai précédent cachait les onglets | `go_to_history()` ferme ce qui couvre l'écran (plusieurs tentatives) |

**Ce qui est validé et ce qui ne l'est pas.** Les jours n° 26 et n° 59 ont été joués de bout en bout en réel. Les
correctifs 4 et 5 ont été codés et testés unitairement (50 tests), puis relancés en réel, mais **la série de deux
jours d'affilée n'a pas été menée à son terme avant la publication** : à vérifier au prochain lancement.

Autre fait utile : pendant ces essais, Chrome a affiché sur l'émulateur l'écran « Continuer en tant que… » avec un compte
Google déjà connecté sur l'appareil. Le bot n'y a pas touché et ne doit jamais le faire ; c'est la raison d'être de
`ensure_app()`. Pour éviter toute exposition, **utiliser un compte Google jetable sur l'émulateur**.

