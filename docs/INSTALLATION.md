# Installation de toute la chaîne

Procédure pour repartir d'un poste Windows 11 vierge. Chaque commande ci-dessous a été **exécutée telle quelle**
pendant la session du 30/09/2026, une par une ; la procédure complète n'a pas été rejouée d'un seul bloc sur une
machine neuve. Aucune étape ne demande de droits administrateur, hors l'activation éventuelle de la virtualisation.

Durée estimée : 30 à 40 minutes, dont 10 à 15 de téléchargements (environ 5 Go au total).

## 0. Prérequis à vérifier

| Élément | Vérification | Remarque |
|---|---|---|
| Virtualisation matérielle | `(Get-CimInstance Win32_ComputerSystem).HypervisorPresent` doit renvoyer `True` | Sinon l'activer dans le BIOS (VT-x / AMD-V) et activer « Plateforme de machine virtuelle » |
| Espace disque | 15 Go libres | SDK + image système + émulateur ≈ 4 Go ; modèle bge-m3 1,2 Go ; vecteurs 164 Mo |
| Python 3.12 | `python --version` | Avec `pip` |
| GPU (facultatif) | — | Sert uniquement à calculer les vecteurs plus vite (quelques minutes sur RTX 5080) ; sur processeur seul, compter plus longtemps |

## 1. Java (portable, sans installation système)

Les outils Android en ligne de commande exigent un JDK. Le paquet `winget` Temurin ne s'installe pas en mode
utilisateur (`No applicable installer found`) : on prend l'archive.

```powershell
$d = "$env:LOCALAPPDATA\Android"; New-Item -ItemType Directory -Force $d | Out-Null
Invoke-WebRequest "https://api.adoptium.net/v3/binary/latest/17/ga/windows/x64/jdk/hotspot/normal/eclipse" -OutFile "$d\jdk17.zip"
Expand-Archive "$d\jdk17.zip" "$d\jdk" -Force
```

## 2. SDK Android en ligne de commande

Le nom de l'archive change à chaque version : il faut le lire sur la page officielle.

```powershell
$d = "$env:LOCALAPPDATA\Android"; $sdk = "$d\Sdk"
New-Item -ItemType Directory -Force "$sdk\cmdline-tools" | Out-Null
$page = (Invoke-WebRequest "https://developer.android.com/studio" -UseBasicParsing).Content
$zip  = ([regex]::Matches($page, 'commandlinetools-win-[0-9]+_latest\.zip') | Select-Object -First 1).Value
Invoke-WebRequest "https://dl.google.com/android/repository/$zip" -OutFile "$d\clt.zip"
Expand-Archive "$d\clt.zip" "$sdk\cmdline-tools" -Force
Rename-Item "$sdk\cmdline-tools\cmdline-tools" latest      # le dossier doit s'appeler « latest »
```

(Version utilisée lors de la session : `commandlinetools-win-15859902_latest.zip`.)

## 3. Paquets Android : outils, émulateur, image avec Google Play

```powershell
$d = "$env:LOCALAPPDATA\Android"
$env:JAVA_HOME = (Get-ChildItem "$d\jdk\*" -Directory)[0].FullName
$env:ANDROID_SDK_ROOT = "$d\Sdk"
$sm = "$d\Sdk\cmdline-tools\latest\bin\sdkmanager.bat"
1..30 | ForEach-Object { 'y' } | & $sm --licenses
& $sm "platform-tools" "emulator" "platforms;android-34" "system-images;android-34;google_apis_playstore;x86_64"
```

**Il faut une image `google_apis_playstore`** : c'est elle qui contient le Play Store. L'image `google_apis` seule
n'en a pas.

## 4. Créer et lancer l'émulateur

```powershell
"no" | & "$d\Sdk\cmdline-tools\latest\bin\avdmanager.bat" create avd -n testphone `
    -k "system-images;android-34;google_apis_playstore;x86_64" -d pixel_7 --force
Start-Process "$d\Sdk\emulator\emulator.exe" -ArgumentList "-avd testphone -no-snapshot -gpu auto"
& "$d\Sdk\platform-tools\adb.exe" wait-for-device
```

Constaté : `avdmanager` affiche deux lignes `Could not load devices … devices.xml` mais l'émulateur se crée et démarre
quand même. Vérification du démarrage complet :

```powershell
& "$d\Sdk\platform-tools\adb.exe" shell getprop sys.boot_completed     # doit afficher 1
& "$d\Sdk\platform-tools\adb.exe" shell pm list packages | Select-String vending   # Play Store présent
```

## 5. Installer Cemanty (étape manuelle)

Dans la fenêtre de l'émulateur : ouvrir le **Play Store**, se connecter à un compte Google (de préférence un compte
jetable), installer Cemanty, le lancer et créer ou ouvrir le compte de jeu. **Ces saisies restent à la main** :
aucun identifiant ne doit passer par le bot ni par le dépôt.

Vérifier que l'appli est bien présente : `adb shell pm list packages | Select-String cemanty`
(paquet attendu : `com.ffprod.cemanty`).

## 6. Ollama et le modèle d'embeddings

1. Installer [Ollama](https://ollama.com/download).
2. Télécharger le modèle (environ 1,2 Go) :
   ```bash
   ollama pull bge-m3
   ```
3. Vérifier que le service répond : `curl http://127.0.0.1:11434/api/tags` doit lister `bge-m3`.

Ollama n'est nécessaire **que pour l'étape 8**. Une fois `emb.npy` produit, on peut l'arrêter.

## 7. Le projet Python

```bash
git clone https://github.com/THBORDIER/cemankill.git
cd cemankill
pip install -r requirements.txt
```

## 8. Construire les vecteurs de mots (une seule fois)

```bash
python cemankill/get_wordlist.py      # liste de fréquence des 50 000 mots (≈ 650 Ko)
python cemankill/embed.py 40000       # appelle Ollama ; produit data/emb.npy (164 Mo) et data/vocab.txt
```

Sortie attendue : une progression `0 40000`, `2000 40000`… puis `ok (40000, 1024)`.

## 9. Premier lancement

Conditions : émulateur démarré, Cemanty installée et connectée, écran **déverrouillé** (le bot ne touche pas au
verrouillage).

```bash
python cemankill/bot.py --days 1
```

Le bot ouvre l'onglet Historique, prend le premier jour non joué, achète un jeton avec une pub si besoin, joue
jusqu'à la victoire, puis s'arrête. `data/bot.log` garde la trace ; `data/obs.json` garde tous les scores.

## Dépannage

| Symptôme | Cause et remède |
|---|---|
| `adb` introuvable | Le bot cherche `%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe` ; ajuster `ADB` en tête de `bot.py` si le SDK est ailleurs |
| `no devices/emulators found` | L'émulateur n'a pas fini de démarrer : attendre `sys.boot_completed = 1` |
| Le bot « tape dans le vide » | L'appli n'est plus sur l'écran attendu (popup, pub). Il s'arrête seul après 25 itérations sans progrès ; relancer avec `--resume` si une partie est ouverte |
| La croix des pubs n'est pas touchée | Écran différent de 1080×2400 : ajuster `CLOSE_XY` |
| Mots refusés en boucle | Normal pour quelques mots ; au-delà de 25 refus d'affilée le bot s'arrête |
| Ne jamais utiliser | `taskkill /IM python.exe` ou équivalent : cibler le processus par son PID |
