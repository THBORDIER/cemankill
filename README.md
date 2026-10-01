# cemankill

Un bot qui joue à **Cemanty** (jeu de mots sémantique quotidien), **sans IA générative pendant la partie**.
Il choisit ses mots avec des vecteurs calculés une fois. Deux pilotes sont disponibles : Android pour les archives,
et navigateur pour le mot quotidien et son bonus.

> Projet de test et d'expérimentation, réalisé le 30/09/2026 à la demande du concepteur de l'appli.
> Le pilote Android ne joue que les archives. Le pilote web peut utiliser soit son profil invité isolé, soit un
> profil de compte explicitement connecté par l'utilisateur. Voir [l'éthique](docs/ARCHITECTURE.md#4-périmètre-et-éthique).

**Vous êtes le créateur de l'application ? Commencez par [docs/RAPPORT-CREATEUR.md](docs/RAPPORT-CREATEUR.md)** :
un résumé sans jargon de ce qui a été fait, constaté et recommandé.

## Ce que contient le dépôt

| Chemin | Rôle |
|---|---|
| `cemankill/` | Le paquet Python, un module par responsabilité (voir ci-dessous) |
| `browser_bot/` | Le pilote Playwright de `cemanty.fr`, indépendant d'Android et d'`adb` |
| `tests/` | 75 tests unitaires, sans Android ni Ollama (faux appareils) |
| `cemankill/embed.py`, `get_wordlist.py` | Scripts à lancer une fois : liste de mots, puis embeddings via Ollama |
| `docs/RAPPORT-CREATEUR.md` | **Résumé sans jargon pour le créateur de l'appli** : ce qui a été fait, constats, risques |
| `docs/INSTALLATION.md` | **Procédure complète** : JDK, SDK Android, émulateur, Ollama, vecteurs, premier lancement |
| `docs/ARCHITECTURE.md` | Comment ça marche, pièce par pièce, et ce qui a été vérifié |
| `docs/REVUE-JEU.md` | Avis sur le jeu : UX, bugs constatés, mesures de fluidité |
| `docs/JOURNAL.md` | Déroulé chronologique de la session, erreurs comprises |
| `CHANGELOG.md` | Historique des versions |
| `data/` | Fichiers générés (non versionnés : `emb.npy` pèse 164 Mo) |

## Démarrage rapide

Installation complète de la chaîne Android : [docs/INSTALLATION.md](docs/INSTALLATION.md).
Les deux pilotes utilisent Python 3.12, [Ollama](https://ollama.com) et les mêmes embeddings. Android demande le
SDK, `adb`, un émulateur Google Play et un compte Cemanty ; le pilote web demande seulement Edge ou Chrome.

```bash
pip install -r requirements.txt
ollama pull bge-m3                       # ~1,2 Go, une seule fois
python cemankill/get_wordlist.py         # liste de mots
python cemankill/embed.py 40000          # produit data/emb.npy et data/vocab.txt
python -m cemankill --days 3             # joue les 3 prochains jours d'archive
python -m browser_bot --check --headless # verifie la version web sans jouer
python -m browser_bot                    # joue le mot quotidien dans Edge
python -m browser_bot --all-sessions     # joue aussi le bonus gratuit
```

Options de `python -m cemankill` : `--days N` (nombre de jours à jouer), `--max-guesses N` (plafond par mot, 250 par défaut),
`--resume` (une partie est déjà ouverte à l'écran). Journal : `data/bot.log` ; tous les scores observés :
`data/obs.json`.

Le pilote web utilise par défaut un profil invité dédié dans `data/browser-profile`. Le lanceur Windows utilise
le profil séparé `data/account-profile`, que l'utilisateur connecte lui-même. Voir
[`browser_bot/README.md`](browser_bot/README.md) pour les options et les garde-fous.

Le bilan détaillé de la mise au point et des essais du 1er octobre est dans
[`docs/DEBRIEF-2026-10-01.md`](docs/DEBRIEF-2026-10-01.md).

## Organisation du code

| Module | Rôle | Dépend d'adb ? |
|---|---|---|
| `config.py` | Constantes : chemins, coordonnées, textes à reconnaître | non |
| `device.py` | `AdbDevice` : taper, balayer, lire l'écran. Seule couche qui parle au système | **oui** |
| `screen.py` | Analyse de l'arbre d'accessibilité : `Screen`, `GameState` | non |
| `solver.py` | Choix du prochain mot (régression à noyau) | non |
| `text.py` | Accents et formes voisines (pluriels) | non |
| `storage.py` | Enregistrement des scores (`obs.json`), écriture atomique | non |
| `game.py` | `Player` : jouer un mot, pubs, succès, mots refusés | non (reçoit un appareil) |
| `navigation.py` | Historique → jour non joué → jeton/pub → partie | non (reçoit un appareil) |
| `cli.py` | Ligne de commande | oui (assemblage) |

Tout sauf `device.py` se teste avec un faux appareil : c'est ce que font les tests.

## Tests

```bash
pip install -r requirements.txt
python -m pytest -q
```

## Ce que fait vraiment le solveur

À chaque essai, le jeu renvoie un score de proximité avec le mot secret. Le bot garde tous les couples
(mot, score) et cherche, dans l'espace des embeddings, la direction qui explique ces scores (régression à noyau),
puis propose le mot le plus proche de cette direction. Pas de LLM, pas de serveur qui tourne en continu : deux
fichiers lus en mémoire, quelques millisecondes de calcul par essai. Le détail est dans
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Résultats

Voir [docs/JOURNAL.md](docs/JOURNAL.md) : nombre d'essais par mot, vitesse, échecs rencontrés. Les chiffres y sont
mesurés, pas estimés.

## Limites

- L'écran est lu par l'arbre d'accessibilité : un changement d'interface de l'appli peut casser le parcours
  (les textes recherchés sont en français).
- La croix des publicités est touchée à une coordonnée fixe (`CLOSE_XY`, écran 1080×2400).
- Les mots sont saisis sans accent (`adb input text` est limité à l'ASCII) ; l'appli les normalise.
- Les publicités rencontrées étaient des annonces de test Google.
