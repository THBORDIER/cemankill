# Rapport de test de Cemanty, à l'attention de son créateur

Ce document résume, sans jargon, ce qui a été fait avec l'application le 30/09/2026, ce qui a été constaté, et ce
que cela peut vous apporter. Le détail technique est dans les autres documents du dépôt ; vous n'avez pas besoin
de les lire pour comprendre celui-ci.

## 1. Ce qui a été fait

À votre demande, l'application (version 0.5.3, Android) a été testée sur un **téléphone virtuel** installé sur un
ordinateur. Trois choses ont été faites :

1. **Une prise en main manuelle** : parcours de l'application, mot bonus, archives, publicités, succès, historique.
2. **Des mesures de fluidité** : images affichées, temps d'affichage, mémoire.
3. **Un petit robot** qui joue seul aux archives : il choisit ses mots à l'aide d'une liste de 40 000 mots français et de
   leur proximité de sens, lit l'écran, ferme les publicités et enchaîne les jours. Il **n'utilise pas d'intelligence
   artificielle pendant la partie**, seulement un calcul sur un fichier.

Ce qui a été volontairement laissé de côté : le mot du jour, les duels, le classement et la série. Le robot ne joue
que les **archives**, qui ne comptent ni pour le classement ni pour la série.

## 2. Ce que le robot a réussi

| Jour | Mot | Résultat |
|---|---|---|
| Mot bonus du jour | album | trouvé à la main, 31 essais |
| 28 septembre | hélicoptère | trouvé à la main, 33 essais |
| 27 septembre | toxine | trouvé par le robot |
| 26 septembre | — | en cours au moment de la rédaction (voir `JOURNAL.md` pour la suite) |

Le cycle « plus de jeton → regarder une publicité → recevoir un jeton → jouer » a fonctionné de bout en bout sans
intervention. Un jour d'archive se joue en quelques minutes.

## 3. Ce qui a été constaté dans l'application

Du plus utile au moins utile. Chaque point a été observé directement.

### À corriger en priorité

1. **Le succès « Marathonien » cache son propre bouton.** Il s'affiche à la 100ᵉ proposition, donc pendant que le
   clavier est ouvert. Le clavier recouvre les boutons « Partager » et « Continuer » : le joueur ne voit pas
   comment fermer la fenêtre. *Piste* : fermer le clavier à l'ouverture d'un succès.
2. **Un message d'erreur qui induit en erreur.** Après une série rapide d'essais, l'application a affiché « Impossible
   de joindre le serveur… vérifie ta connexion », alors que la connexion fonctionnait. Il s'agit peut-être d'une limite
   de débit côté serveur (non confirmé). *Piste* : un message du type « Trop vite, réessaie dans un instant ».

### À savoir

3. **Les archives sont très lentes à rattraper pour un joueur qui n'est pas abonné.** Un jeton coûte une publicité
   vidéo en deux parties, et on n'en reçoit qu'un par jour (sept au maximum). Avec une soixantaine de jours en retard,
   le rattrapage complet est pratiquement réservé à l'abonnement. C'est un choix commercial cohérent, mais il peut
   décourager un nouvel arrivant.
4. **Les mots refusés ne disent pas pourquoi.** Le mot reste dans le champ. Un message (« mot inconnu ») aiderait.
5. **Singulier et pluriel donnent le même score** (par exemple « animal » et « animaux »), ce qui fait perdre un essai
   aux joueurs qui ne le savent pas. Ce n'est pas un défaut du jeu en soi ; une petite indication le rendrait
   transparent.

### Ce qui plaît

- La mascotte Emby, qui réagit à la partie, et l'ensemble visuel, chaleureux et cohérent.
- Le retour sur chaque essai : score, « température », jauge, et le repère « porte du top 1000 ».
- Le top 1000 montré après la victoire : on y apprend comment le modèle raisonne.
- La saisie tolérante : un mot sans accent est reconnu.
- Un démarrage court et une visite guidée claire.

### Fluidité (mesurée sur téléphone virtuel, donc indicative)

Aucune image saccadée sur 82 images mesurées pendant des défilements répétés ; temps d'affichage d'environ 21 ms ;
mémoire d'environ 26 Mo (partie Java) et 29 Mo (partie native). Rien d'inquiétant. Non mesuré : le démarrage à froid, la batterie, un téléphone d'entrée de
gamme.

## 4. Ce que le test révèle sur la protection de votre jeu

Ces points ne sont pas des reproches : ils montrent ce qu'un robot peut faire, donc ce qu'un joueur malin pourrait
faire.

- **L'application se laisse lire en entier par un programme.** Tous les textes de l'écran sont accessibles, ce qui est
  très bien pour les personnes malvoyantes mais rend l'automatisation simple. Il n'y a aucune protection contre un
  joueur automatique : le robot a joué sans qu'aucune alarme ne se déclenche.
- **Le robot ferme les publicités dès que la croix apparaît.** Les annonces rencontrées étaient des **annonces de test**
  de Google (étiquette « Test Ad »). Avec de vraies régies publicitaires, un programme qui visionne ou ferme des
  annonces de façon automatique est considéré comme du **trafic invalide** et peut entraîner la suspension d'un compte
  publicitaire. **Ne faites donc pas tourner ce robot sur une version avec de vraies publicités.**
- **Le rythme des essais n'est pas limité** côté application (le robot joue environ 16 essais par minute). Si le
  classement ou les duels deviennent un enjeu, une limite de cadence serait à envisager.
- **Les jetons d'archive** peuvent être obtenus en boucle tant que des publicités de test sont servies ; à
  vérifier sur une version de production.

## 5. Ce que contient le dépôt et comment le lire

| Si vous voulez… | Lisez |
|---|---|
| Comprendre le principe du robot | `docs/ARCHITECTURE.md` |
| Le revoir fonctionner sur votre ordinateur | `docs/INSTALLATION.md` (procédure complète) |
| Tous les constats détaillés sur l'appli | `docs/REVUE-JEU.md` |
| Le déroulé de la journée, erreurs comprises | `docs/JOURNAL.md` |

Les comptes, mots de passe et identifiants ne figurent nulle part dans le dépôt. Le compte de test utilisé
existe dans l'application ; les parties jouées par le robot y apparaissent dans l'historique et les statistiques.

## 6. Limites honnêtes de ce test

- Un seul appareil virtuel, un seul compte, une seule journée.
- Publicités de test uniquement.
- Pas de test de charge, de sécurité du serveur, de hors-ligne ni de batterie.
- Les causes citées pour l'erreur « serveur injoignable » et pour le débit sont des hypothèses, pas des constats.
