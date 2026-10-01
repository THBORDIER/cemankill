# Bot navigateur

Ce dossier contient le pilote de la version web de Cemanty. Il reutilise `cemankill.solver.Solver`, les fichiers
`data/emb.npy` et `data/vocab.txt`, mais ne depend ni d'Android ni d'`adb`.

```powershell
python -m pip install -r requirements.txt
python -m browser_bot --check --headless   # verifie le site sans jouer
python -m browser_bot                      # joue dans une fenetre Edge dediee
python -m browser_bot --all-sessions       # mot du jour puis bonus gratuit
python -m browser_bot --archives           # enchaine les jours manques de l'historique
python -m browser_bot --all-sessions --watch --headless  # veille autonome entre les jours
python -m browser_bot.tray                    # icone Windows, demarrage/arret et journal
```

Le profil invite est conserve dans `data/browser-profile`, ce qui permet de reprendre une partie interrompue.
Les observations sont ecrites dans `data/web_obs.json`, les mots refuses dans `data/web_banned.json` et le journal
dans `data/browser_bot.log`.

Le pilote :

- passe le tutoriel puis choisit explicitement `Continuer en invite` ;
- cible le vrai champ Compose, saisit le mot par frappes et valide avec `Entree` sans cliquer sur le canvas ;
- lit le numero du mot, l'essai et le score depuis le texte d'accessibilite ;
- n'autorise que `https://cemanty.fr/jouer/`, refuse les marqueurs publicitaires et toute iframe visible, puis ferme
  sa session si une navigation externe ou une publicite survient ;
- avec `--all-sessions`, ouvre le mot bonus gratuit par ses boutons nommes ; les archives ne sont traitees que si
  `--archives` est egalement present ;
- avec `--archives`, ouvre `Rattraper un jour manque`, remonte les mois et ne selectionne que les lignes
  `Mot a trouver` / `A jouer`; un jeton manquant peut etre obtenu par le bouton Cemanty nomme de publicite
  recompensee ; le bot ne clique jamais dans le contenu de l'annonce, ferme toute fenetre externe et n'utilise
  que les controles de fermeture explicitement nommes `Close ad` ou `Fermer la publicite` ;
- avec `--watch`, reconnait l'ecran `PROCHAIN MOT DANS`, ne clique rien pendant l'attente et recharge seulement
  `/jouer/` jusqu'a l'apparition du prochain plateau ;
- ne saisit ni identifiant ni mot de passe ; le lanceur peut reutiliser `data/account-profile` uniquement lorsque
  l'utilisateur l'a lui-meme connecte ;

La version web invite donne acces au mot quotidien. Le 01/10/2026, Cemanty a bloque sa poursuite apres 29 essais
invites et demande la creation ou la connexion d'un compte. Le bot s'arrete explicitement dans cet etat ; il ne
cree pas de profils invites supplementaires pour contourner cette limite. Avec le profil de compte dedie connecte
par l'utilisateur, le bot a valide le mot quotidien et le bonus, puis parcouru l'historique. L'ouverture effective
d'une archive n'a pas pu etre validee ce jour-la : le compte avait 0 jeton et Cemanty ne proposait aucune publicite,
sur le Web comme sur Android.

Les profils Playwright sont strictement distincts du navigateur personnel. Une session de compte deja ouverte
dans un autre navigateur n'est jamais copiee : aucun cookie, jeton ou mot de passe n'est lu ou exporte.

Sous Windows, `python -m browser_bot.tray` ajoute une flamme orange dans la zone de notification. Le menu permet
de demarrer ou d'arreter uniquement le PID du bot, d'afficher ou masquer sa fenetre Edge avec le meme profil de
compte dedie, et de consulter le journal. Il n'ouvre jamais le navigateur Windows par defaut. Quitter l'icone
arrete aussi le bot et ses processus navigateur enfants. Le PID est associe a son heure de creation Windows afin
qu'un ancien fichier ne puisse jamais viser un autre processus apres redemarrage.
