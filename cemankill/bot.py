"""Cemanty bot : joue les archives sur l'emulateur Android (adb) sans LLM a l'execution.

Lecture de l'ecran = uiautomator dump (texte). Choix des mots = solveur par embeddings (bge-m3 via Ollama, calcules une fois).
Usage : python bot.py [--days N] [--max-guesses 250]
"""
import json, os, re, subprocess, sys, time, unicodedata, argparse
import xml.etree.ElementTree as ET
import numpy as np

ADB = os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe")
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
CLOSE_XY = (1037, 207)          # croix des pubs (coin haut droit)
SEEDS = ["maison", "animal", "eau", "voiture", "amour", "temps", "nourriture", "guerre", "musique",
         "corps", "argent", "nature", "travail", "ville", "sport", "couleur", "religion", "science", "arbre", "peur"]


def adb(*a, timeout=30):
    return subprocess.run([ADB, *a], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout).stdout


def strip(w):
    return "".join(c for c in unicodedata.normalize("NFD", w) if unicodedata.category(c) != "Mn")


class Screen:
    def __init__(self):
        adb("shell", "uiautomator", "dump", "/sdcard/u.xml")
        xml = adb("shell", "cat", "/sdcard/u.xml")
        self.nodes = []
        try:
            for n in ET.fromstring(xml).iter("node"):
                t = n.get("text") or n.get("content-desc") or ""
                m = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", n.get("bounds") or "")
                b = tuple(map(int, m.groups())) if m else (0, 0, 0, 0)
                self.nodes.append((t, n.get("class") or "", b))
        except ET.ParseError:
            pass
        self.t = [n[0] for n in self.nodes if n[0] and n[0] not in ("/1000", "1000")]

    def has(self, s):
        return any(s in t for t in self.t)

    def find(self, s, last=False):
        c = [n for n in self.nodes if s in n[0]]
        if not c:
            return None
        return c[-1] if last else c[0]


def tap_xy(x, y):
    adb("shell", "input", "tap", str(x), str(y))


def tap_node(n):
    b = n[2]
    tap_xy((b[0] + b[2]) // 2, (b[1] + b[3]) // 2)


def tap_text(s, last=False, wait=1.2):
    n = Screen().find(s, last)
    if not n:
        return False
    tap_node(n)
    time.sleep(wait)
    return True


def close_ads(limit=90):
    """Ferme toute pub plein ecran des que la croix est disponible."""
    closed = False
    for _ in range(limit):
        s = Screen()
        if not (s.has("Test Ad") or s.has("Learn More") or s.has("Next Ad") or s.has("Ad 1 of")):
            return closed
        closed = True
        tap_xy(*CLOSE_XY)
        time.sleep(2)
    print("!! pub encore ouverte apres", limit, "essais")
    return closed


class Solver:
    """Regression a noyau (kernel ridge) sur embeddings centres : chaque score observe contraint la direction du mot cible."""
    POOL = 25000       # mots les plus frequents seulement (la cible est un mot courant)
    LAM = 0.15

    def __init__(self):
        E = np.load(os.path.join(DATA, "emb.npy"))
        E = E - E.mean(0)
        self.E = (E / np.linalg.norm(E, axis=1, keepdims=True)).astype(np.float32)
        self.V = open(os.path.join(DATA, "vocab.txt"), encoding="utf-8").read().splitlines()
        self.idx = {w: i for i, w in enumerate(self.V)}
        self.reset()

    def reset(self):
        self.obs = []      # (idx, score)
        self.used = set()
        self.seed_i = 0

    def add(self, i, s):
        self.obs.append((i, s)); self.used.add(i)
        w = self.V[i]
        for v in {w + "s", w + "x", w + "es", w + "e", w.rstrip("sx"), w[:-2] if w.endswith("es") else w, w[:-1] + "aux" if w.endswith("al") else w}:
            j = self.idx.get(v)
            if j is not None:
                self.used.add(j)

    def next(self):
        if len(self.obs) < 6:
            while self.seed_i < len(SEEDS):
                w = SEEDS[self.seed_i]; self.seed_i += 1
                i = self.idx.get(w)
                if i is not None and i not in self.used:
                    return i
        ids = [i for i, _ in self.obs]
        S = np.array([s for _, s in self.obs], dtype=np.float64) / 100.0
        m = S.mean()
        G = self.E[ids].astype(np.float64)
        alpha = np.linalg.solve(G @ G.T + self.LAM * np.eye(len(ids)), S - m)
        pred = self.E[: self.POOL] @ (G.T @ alpha).astype(np.float32)
        pred[[i for i in self.used if i < self.POOL]] = -1e9
        return int(np.argmax(pred))


def save_obs(day, sol):
    p = os.path.join(DATA, "obs.json")
    try:
        d = json.load(open(p, encoding="utf-8"))
    except Exception:
        d = {}
    d[str(day)] = [[sol.V[i], s] for i, s in sol.obs]
    json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False)


def focus_input():
    n = next((n for n in Screen().nodes if n[1] == "android.widget.EditText"), None)
    if n:
        tap_node(n); time.sleep(0.6)


def dismiss_overlays(s):
    """Succes debloque : le bouton Continuer est sous le clavier -> on masque le clavier, on clique, on refocalise le champ."""
    if s.has("SUCCÈS DÉBLOQUÉ") or s.has("SUCCES DEBLOQUE"):
        adb("shell", "input", "keyevent", "KEYCODE_BACK"); time.sleep(0.8)
        tap_text("Continuer", wait=1.0)
        focus_input()
        return True
    return False


def read_state(s=None):
    """(champ_texte, dernier_mot, dernier_score, fini)"""
    s = s or Screen()
    field = ""
    for t, c, _ in s.nodes:
        if c == "android.widget.EditText":
            field = t
    last = score = None
    if "Abandonner" in s.t:
        try:
            i = next(k for k, t in enumerate(s.t) if t.startswith("Mot n"))
            last = s.t[i + 1]; score = float(s.t[i + 3].replace(",", ".").replace("−", "-"))
        except Exception:
            pass
    in_game = "Abandonner" in s.t or any(c == "android.widget.EditText" for _, c, _ in s.nodes)
    overlay = s.has("SUCCÈS DÉBLOQUÉ") or s.has("Test Ad") or s.has("Learn More")
    done = s.has("Terminer") or any(t.startswith("Tu as trouv") for t in s.t) or (not in_game and not overlay)
    return field, last, score, done, s


def play_word(sol, max_guesses, log):
    sol.reset(); day = None
    n = 0; refused = 0; stuck = 0
    while n < max_guesses:
        if stuck > 25:
            log("!! bot bloque (aucune progression), arret"); return None, None
        i = sol.next()
        word = sol.V[i]
        adb("shell", "input", "text", strip(word))
        adb("shell", "input", "keyevent", "KEYCODE_ENTER")
        time.sleep(0.9)
        field, last, score, done, s = read_state()
        if s.has("Test Ad") or s.has("Learn More"):
            close_ads(); field, last, score, done, s = read_state()
        if dismiss_overlays(s):
            field, last, score, done, s = read_state()
        if day is None:
            md = next((re.search(r"n° (\d+)", t) for t in s.t if t.startswith("Mot n")), None)
            day = md.group(1) if md else "?"
        if done:
            return n + 1, word
        if field and not field.startswith("Tape"):            # mot refuse : on vide le champ et on passe
            adb("shell", "input", "keyevent", "KEYCODE_MOVE_END")
            for _ in range(len(field) + 2):
                adb("shell", "input", "keyevent", "KEYCODE_DEL")
            sol.used.add(i); refused += 1; stuck += 1
            continue
        if last is None or score is None:
            stuck += 1; time.sleep(1); continue
        stuck = 0
        n += 1
        sol.add(i, score); save_obs(day, sol)
        if n % 10 == 0:
            best = max(sol.obs, key=lambda o: o[1])
            log(f"   essai {n}: meilleur {sol.V[best[0]]} {best[1]:.1f} (refuses {refused})")
    return None, None


def open_next_archive(log):
    if not tap_text("Historique", last=True, wait=1.5):
        return False
    for _ in range(8):
        s = Screen()
        n = s.find("Mot à trouver")
        if n and 350 < n[2][1] < 2050:
            tap_node(n); time.sleep(1.5); break
        adb("shell", "input", "swipe", "540", "1700", "540", "700", "300"); time.sleep(0.8)
    else:
        return False
    if not tap_text("Jouer ce mot"):
        return False
    time.sleep(1.5)
    s = Screen()
    if s.has("Regarder une pub"):
        log("  plus de jeton -> pub")
        tap_text("Regarder une pub"); time.sleep(4); close_ads()
        time.sleep(1.5)
        if not tap_text("Jouer ce mot"):
            return False
        time.sleep(2)
    s = Screen()
    n = next((n for n in s.nodes if n[1] == "android.widget.EditText"), None)
    if n is None:
        return False
    tap_node(n); time.sleep(0.8)
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=1)
    ap.add_argument("--max-guesses", type=int, default=250)
    ap.add_argument("--resume", action="store_true", help="une partie est deja ouverte a l'ecran")
    a = ap.parse_args()
    logf = open(os.path.join(DATA, "bot.log"), "a", encoding="utf-8")

    def log(m):
        print(m, flush=True); logf.write(m + "\n"); logf.flush()

    sol = Solver()
    for d in range(a.days):
        close_ads()
        if not (a.resume and d == 0) and not open_next_archive(log):
            log("!! impossible d'ouvrir la prochaine archive, arret"); break
        t0 = time.time()
        n, word = play_word(sol, a.max_guesses, log)
        if n is None:
            log(f"!! echec apres {a.max_guesses} essais"); break
        log(f"OK  {word} trouve en {n} essais ({time.time()-t0:.0f}s)")
        tap_text("Terminer", wait=2); close_ads()


if __name__ == "__main__":
    main()
