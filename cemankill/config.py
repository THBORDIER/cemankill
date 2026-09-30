"""Constantes du bot : chemins, coordonnees, textes a reconnaitre. Tout ce qui depend de l'appli ou de l'ecran est ici."""
import os

ADB = os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe")
DATA_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data"))

APP_PACKAGE = "com.ffprod.cemanty"
APP_ACTIVITY = "fr.cemanty.MainActivity"

# Croix des pubs plein ecran (coin haut droit) sur un ecran 1080x2400 ; son texte n'est pas lisible.
CLOSE_XY = (1037, 207)

# Mots d'amorce, volontairement eloignes les uns des autres, pour donner de la matiere a la regression.
SEEDS = ["maison", "animal", "eau", "voiture", "amour", "temps", "nourriture", "guerre", "musique",
         "corps", "argent", "nature", "travail", "ville", "sport", "couleur", "religion", "science", "arbre", "peur"]
MIN_OBS_BEFORE_MODEL = 6     # nombre d'essais d'amorce avant de passer au modele
POOL = 25000                 # seuls les mots les plus frequents sont proposes
RIDGE_LAMBDA = 0.15          # regularisation de la regression a noyau

MAX_STUCK = 25               # iterations sans progres avant arret
AD_MARKERS = ("Test Ad", "Learn More", "Next Ad", "Ad 1 of")
ACHIEVEMENT_MARKERS = ("SUCCÈS DÉBLOQUÉ", "SUCCES DEBLOQUE")
HINT_PREFIX = "Tape"         # texte indicatif du champ de saisie quand il est vide
