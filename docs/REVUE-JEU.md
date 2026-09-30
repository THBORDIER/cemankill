# Revue de Cemanty (v0.5.3, Android)

Test réalisé le 30/09/2026 sur un émulateur Android 14 (Pixel 7, 1080×2400), appli installée depuis le Play Store
(`com.ffprod.cemanty`, versionCode 9, minSdk 32, targetSdk 37). Environ 1 h 30 de jeu, sur un compte de test déjà
créé par le demandeur.

**Méthode et limites.** Tout est parti d'une session pilotée sans écran tactile réel : clics et saisie par `adb`,
lecture de l'écran par captures et par l'arbre d'accessibilité. L'émulateur n'est pas un téléphone : les mesures de
fluidité sont indicatives. Les annonces rencontrées étaient des annonces de test Google. Ce qui n'a pas été
vérifié est signalé comme tel.

## Le jeu en une phrase

Un jeu de mots quotidien à la Cémantix : un mot secret identique pour tous à minuit ; chaque proposition reçoit un
score de proximité sémantique et une « température » ; on cherche jusqu'à trouver, autant d'essais que l'on veut.
Autour : série de jours, gels de série, succès, duels, coop, amis, classement, archives et mot bonus.

## Ce qui fonctionne bien

- **Une identité forte et cohérente.** La mascotte Emby réagit à l'état de la partie (endormie, frigorifiée,
  yeux en étoile à la victoire). Palette chaude, typographie ronde : l'ensemble est reconnaissable et agréable.
- **Un retour d'information riche sans être encombrant.** Chaque essai affiche un score numérique, une
  étiquette de température (Glacial, Très froid, Froid…), une jauge avec un repère, et un séparateur
  « PORTE DU TOP 1000 » qui donne un vrai repère de progression. Le rang « 937/1000 » rend les mots chauds
  immédiatement lisibles.
- **Le top 1000 après la victoire** est une très bonne idée : on apprend comment le modèle « pense ».
- **Saisie tolérante.** L'appli accepte les mots sans accent (`melodie` est reconnu comme `mélodie`).
- **Aides mesurées.** Un indice arrive après un certain nombre d'essais (« Indice dans 9 essais »).
- **Onboarding court** (3 cartes) et visite guidée sur l'historique, le profil et la série, qui explique la règle
  des gels et des jours manqués en une phrase.
- **Accessibilité technique.** Tous les textes de l'interface sont exposés à l'arbre d'accessibilité
  (c'est ce qui permet de tester l'appli sans vision) ; c'est de bon augure pour les lecteurs d'écran. Non
  vérifié avec TalkBack ni pour les contrastes.

## Problèmes constatés (du plus gênant au plus mineur)

1. **Le succès « Marathonien » masque son propre bouton.** Il s'affiche à la 100ᵉ proposition, donc quand le
   clavier est ouvert ; le clavier recouvre « Partager » et « Continuer ». Un joueur doit deviner qu'il faut
   fermer le clavier. Reproduit deux fois. *Correctif suggéré* : fermer le clavier à l'ouverture d'un succès, ou
   ancrer la fenêtre au-dessus du clavier.
2. **Message d'erreur réseau trompeur.** Vers la 40ᵉ proposition, après une série rapide d'essais, l'appli a
   affiché « Impossible de joindre le serveur… vérifie ta connexion » alors que la connexion fonctionnait
   (ping OK, parties suivantes normales). Cause probable, non confirmée : limitation de débit côté serveur.
   Dans ce cas le message devrait dire « trop vite, réessaie dans un instant ».
3. **Pression publicitaire forte sur les archives.**
   - Une pub plein écran suit chaque fin de partie ; la croix n'apparaît qu'au bout de 5 à 10 secondes.
   - Rejouer un jour passé coûte 1 jeton ; on en reçoit 1 par jour (7 au plus) ; un jeton de plus demande une
     pub vidéo en **deux parties** (« Ad 1 of 2 ») d'environ 30 secondes ; l'alternative est l'abonnement
     Cemanty+. Avec une soixantaine de jours à rattraper, l'archive est pratiquement réservée aux abonnés.
     C'est un choix commercial assumé, mais il est à connaître.
4. **Les mots refusés ne sont pas expliqués** (constaté : le champ reste rempli). Non vérifié : si un message
   apparaît à l'écran ; dans le doute, un joueur ne sait pas si son mot est inconnu, mal orthographié ou
   bloqué.
5. **Le modèle de proximité est bruité.** Le top 1000 de « album » contient « killers », « skeud »,
   « masterisé », « hard-rock », « réenregistrer » ; singulier et pluriel donnent exactement le même score
   (`animal` et `animaux` : 19,35). Ce n'est pas un défaut en soi (c'est la nature du modèle), mais les
   formes fléchies comptent comme des essais « perdus » pour un joueur qui ne le sait pas.
6. **Parcours de retour en arrière incohérent en début d'appli.** Depuis l'écran de connexion, le retour arrière
   ramène à une étape d'onboarding déjà passée (autorisation des notifications), puis à l'appli. Mineur ; à
   confirmer sur un parcours utilisateur réel, mes manipulations ayant pu provoquer le cas.

## Performances et fluidité (émulateur, indicatif)

Mesures par `adb shell dumpsys gfxinfo` et `meminfo`, pendant des défilements répétés de la liste de résultats :

| Mesure | Résultat |
|---|---|
| Images rendues | 82 |
| Images « janky » (nouvelle mesure Android) | 0 (0 %) |
| Durée d'une image | médiane 21 ms, p90 22 ms, p99 25 ms |
| Vsync manqués / UI thread lent / chargements de bitmap lents | 0 / 0 / 0 |
| Mémoire : tas Java / tas natif | 26 Mo / 29 Mo |

Lecture : rien d'inquiétant. La médiane à 21 ms correspond à la cadence de l'émulateur, pas à la limite de
l'appli. **Non mesuré** : démarrage à froid, consommation de batterie, comportement hors ligne, tenue sur
téléphone d'entrée de gamme.

## Verdict

Un jeu réussi dans son genre : bonne lisibilité du score, identité soignée, structure sociale complète. Les
deux points à traiter en priorité sont le **succès qui masque son bouton** (bug) et le **message réseau
trompeur** (clarté). La **pression publicitaire sur les archives** est le principal risque de rétention pour un
joueur qui découvre le jeu en retard.
