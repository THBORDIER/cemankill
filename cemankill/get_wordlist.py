"""Telecharge la liste de 50 000 mots francais (frequences OpenSubtitles, projet FrequencyWords) dans data/."""
import os, urllib.request
URL = "https://raw.githubusercontent.com/hermitdave/FrequencyWords/master/content/2018/fr/fr_50k.txt"
DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
os.makedirs(DATA, exist_ok=True)
urllib.request.urlretrieve(URL, os.path.join(DATA, "fr_50k.txt"))
print("ok")
