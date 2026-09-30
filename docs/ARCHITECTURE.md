# Architecture de cemankill

Ce document décrit **comment** le bot joue et **pourquoi** chaque pièce existe. Il distingue ce qui a été
vérifié en réel (sur l'émulateur) de ce qui relève d'une hypothèse.

## Vue d'ensemble

```
            ┌────────────────────────── une seule fois ──────────────────────────┐
            │  fr_50k.txt  ──►  embed.py  ──►  Ollama (bge-m3)  ──►  emb.npy      │
            │  (mots + fréquences)           (mot → 1024 nombres)    vocab.txt    │
            └─────────────────────────────────────────────────────────────────────┘

   Pendant le jeu (Ollama n'a plus besoin de tourner) :

   ┌──────────┐  propose un mot   ┌──────────┐   adb input text    ┌───────────────┐
   │ Solver   │ ────────────────► │  bot.py  │ ──────────────────► │  Émulateur    │
   │ (numpy)  │ ◄──────────────── │  (boucle)│ ◄────────────────── │  Android +    │
   └──────────┘  score observé    └──────────┘   uiautomator dump  │  appli Cemanty│
                                                  (texte de l'écran)└───────────────┘
```

Aucun LLM n'intervient pendant la partie. Les seuls composants « ML » sont les vecteurs de mots, calculés une
fois et stockés dans un fichier.

## 1. Les embeddings (`embed.py`)

Un *embedding* associe à chaque mot une liste de nombres (ici 1024) telle que deux mots de sens proche ont des
listes proches. Le modèle utilisé est **bge-m3**, servi par **Ollama** en local (RTX 5080, quelques minutes pour
40 000 mots).

- Entrée : `data/fr_50k.txt`, liste de fréquence OpenSubtitles (projet *FrequencyWords*), téléchargée par
  `get_wordlist.py`.
- Filtrage : lettres françaises uniquement, 3 à 16 caractères, pas de doublon.
- Sortie : `data/emb.npy` (40 000 × 1024, `float32`, environ 164 Mo) et `data/vocab.txt` (un mot par ligne,
  par ordre de fréquence décroissante).
- Ce n'est **ni une base de données, ni un serveur** : deux fichiers lus en mémoire par numpy. Ils ne sont pas
  versionnés (trop gros, reconstructibles).

## 2. Le solveur (`bot.py`, classe `Solver`)

Le jeu répond à chaque essai par un **score de proximité** avec le mot secret (un pourcentage de similarité
cosinus, qui peut être négatif). Le jeu utilise son propre modèle, différent de bge-m3 : les valeurs ne sont donc
pas directement comparables. Le solveur n'a besoin que d'une chose : que les deux modèles **ordonnent à peu près
pareil** les mots.

Méthode (régression à noyau, *kernel ridge*) :

1. Les vecteurs sont **centrés** (on retire le vecteur moyen) puis normalisés. Sans cela, tous les mots ont des
   similarités comprises entre 0,4 et 0,8 et le signal est noyé.
2. Pour les `k` mots déjà essayés `g_1 … g_k` avec leurs scores `s_1 … s_k`, on cherche une direction `t`
   telle que `⟨t, g_i⟩ ≈ s_i`. Avec `k` bien inférieur à 1024, la solution de norme minimale s'écrit
   `t = Σ αᵢ gᵢ` avec `α = (G·Gᵀ + λI)⁻¹ (s − s̄)`, `λ = 0,15`.
3. Le prochain mot est celui, parmi les **25 000 plus fréquents** non encore essayés, qui maximise `⟨c, t⟩`.
4. Les 6 premiers essais sont des mots d'amorce volontairement éloignés les uns des autres (maison, animal,
   eau, voiture, amour, temps…), pour que la régression ait de quoi travailler.

Chaque score observé est **enregistré sur disque** (`data/obs.json`, par numéro de jour) après chaque essai.

Limites connues :

- Modèle différent du jeu ⇒ le solveur approche la cible mais peut tourner autour (ce qui a été constaté avec
  une première version qui évaluait chaque mot isolément ; la version actuelle utilise tous les scores ensemble).
- Le jeu accepte des formes fléchies et des mots rares ; la liste de 40 000 mots n'est pas exhaustive.
- L'information « le mot est dans le top 1000 (rang 937/1000) » affichée par le jeu n'est **pas encore
  exploitée** : c'est la piste d'amélioration la plus rentable.

## 3. Le pilotage (`bot.py`, fonctions `adb`, `Screen`, `play_word`)

| Besoin | Méthode | Vérifié |
|---|---|---|
| Lire l'écran | `adb shell uiautomator dump` puis analyse XML : tous les textes de l'interface sont disponibles (l'appli expose son arbre d'accessibilité). Bien moins coûteux qu'une capture d'écran. | oui |
| Taper un mot | `adb shell input text` (ASCII uniquement) + `KEYCODE_ENTER`. Les accents sont retirés ; l'appli retrouve le mot accentué (`melodie` → `mélodie`). | oui |
| Détecter un mot refusé | Après l'envoi, le champ de saisie n'est pas vidé : on le vide (touches Suppr) et on écarte le mot. Sans ce contrôle, les mots suivants s'accolaient au mot refusé. | oui |
| Lire le résultat d'un essai | L'en-tête de la partie affiche le **dernier** mot essayé et son score. | oui |
| Fermer les pubs plein écran | Détection du texte `Test Ad` / `Learn More` / `Next Ad`, puis tap sur la croix en haut à droite (1037, 207 sur un écran 1080×2400), répété jusqu'à disparition. La croix n'apparaît qu'après 5 à 10 secondes. | oui |
| Fermer un succès débloqué | Le bouton `Continuer` est **caché par le clavier** : on masque le clavier (`KEYCODE_BACK`), on touche `Continuer`, on redonne le focus au champ. | oui |
| Enchaîner les archives | Onglet Historique → premier jour « Mot à trouver » → « Jouer ce mot » → si plus de jeton : « Regarder une pub » (pub fermée automatiquement) → re-« Jouer ce mot ». | partiel |
| Garde-fous | Plus de 25 itérations sans progrès ⇒ arrêt avec message ; plafond d'essais par mot (`--max-guesses`). | oui |

### Coordonnées d'écran

Les actions de pilotage utilisent soit le centre d'un élément trouvé par son texte (robuste), soit une
coordonnée fixe (seulement pour la croix des pubs, dont le texte n'est pas lisible). L'émulateur est un
Pixel 7 en 1080×2400 : sur un autre écran, ajuster `CLOSE_XY`.

## 4. Périmètre et éthique

- Le bot ne joue **que les archives** (jours passés, hors classement et hors série). Il ne touche ni au mot du
  jour, ni aux duels, ni au classement : tricher sur un jeu compétitif n'a pas de sens ici et n'est pas le but.
- L'application testée appartient à un proche de l'auteur, qui a demandé le test. Le dépôt ne contient aucun
  identifiant, aucun compte, aucun jeton.
- Les publicités rencontrées sont des **annonces de test Google** (étiquette `Test Ad`) : le comportement avec de
  vraies régies n'a pas été observé.

## 5. Reconstruire de zéro

```bash
pip install -r requirements.txt
ollama pull bge-m3
python cemankill/get_wordlist.py
python cemankill/embed.py 40000      # ~ quelques minutes, produit data/emb.npy et data/vocab.txt
python cemankill/bot.py --days 1     # l'émulateur doit tourner, l'appli Cemanty ouverte sur l'historique
```
