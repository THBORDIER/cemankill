# cemankill

Un bot qui joue à **Cemanty** (jeu de mots sémantique quotidien, Android) sur un émulateur, **sans IA générative
pendant la partie**. Il choisit ses mots avec des vecteurs de mots (embeddings) calculés une fois, lit l'écran
en texte via `adb`, ferme tout seul les publicités et enchaîne les jours d'archive.

> Projet de test et d'expérimentation, réalisé le 30/09/2026 à la demande du concepteur de l'appli.
> Le bot ne joue **que les archives** (hors classement et hors série). Voir [l'éthique](docs/ARCHITECTURE.md#4-périmètre-et-éthique).

**Vous êtes le créateur de l'application ? Commencez par [docs/RAPPORT-CREATEUR.md](docs/RAPPORT-CREATEUR.md)** :
un résumé sans jargon de ce qui a été fait, constaté et recommandé.

## Ce que contient le dépôt

| Chemin | Rôle |
|---|---|
| `cemankill/bot.py` | Le bot : pilotage `adb`, lecture d'écran, solveur, fermeture des pubs et des succès |
| `cemankill/embed.py` | Calcule les embeddings des 40 000 mots (une seule fois, via Ollama) |
| `cemankill/get_wordlist.py` | Télécharge la liste de mots français par fréquence |
| `docs/RAPPORT-CREATEUR.md` | **Résumé sans jargon pour le créateur de l'appli** : ce qui a été fait, constats, risques |
| `docs/INSTALLATION.md` | **Procédure complète** : JDK, SDK Android, émulateur, Ollama, vecteurs, premier lancement |
| `docs/ARCHITECTURE.md` | Comment ça marche, pièce par pièce, et ce qui a été vérifié |
| `docs/REVUE-JEU.md` | Avis sur le jeu : UX, bugs constatés, mesures de fluidité |
| `docs/JOURNAL.md` | Déroulé chronologique de la session, erreurs comprises |
| `CHANGELOG.md` | Historique des versions |
| `data/` | Fichiers générés (non versionnés : `emb.npy` pèse 164 Mo) |

## Démarrage rapide

Installation complète de la chaîne (émulateur compris) : [docs/INSTALLATION.md](docs/INSTALLATION.md).
Résumé, si tout est déjà en place. Prérequis : Windows, Python 3.12, [Ollama](https://ollama.com), un émulateur Android avec Google Play
(SDK Android + `adb`), l'appli Cemanty installée et connectée à un compte.

```bash
pip install -r requirements.txt
ollama pull bge-m3                       # ~1,2 Go, une seule fois
python cemankill/get_wordlist.py         # liste de mots
python cemankill/embed.py 40000          # produit data/emb.npy et data/vocab.txt
python cemankill/bot.py --days 3         # joue les 3 prochains jours d'archive
```

Options de `bot.py` : `--days N` (nombre de jours à jouer), `--max-guesses N` (plafond par mot, 250 par défaut),
`--resume` (une partie est déjà ouverte à l'écran). Journal : `data/bot.log` ; tous les scores observés :
`data/obs.json`.

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
