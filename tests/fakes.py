"""Faux appareils et monde synthetique pour tester sans Android ni Ollama."""
import numpy as np

from cemankill import config
from cemankill.screen import Screen


def make_xml(nodes) -> str:
    """nodes : liste de (texte, classe, (x1, y1, x2, y2))."""
    body = "".join(
        f'<node text="{t}" content-desc="" class="{c}" bounds="[{b[0]},{b[1]}][{b[2]},{b[3]}]"/>' for t, c, b in nodes)
    return f"<hierarchy>{body}</hierarchy>"


def screen_of(*texts, edit=None) -> Screen:
    nodes = [(t, "android.widget.TextView", (0, 0, 10, 10)) for t in texts]
    if edit is not None:
        nodes.append((edit, "android.widget.EditText", (0, 0, 10, 10)))
    return Screen.from_xml(make_xml(nodes))


def make_world(n_words=2500, dim=64, noise=0.35, seed=0):
    """Vocabulaire synthetique + 'modele du jeu' = vecteurs du solveur bruites (les deux modeles different, comme en vrai)."""
    rng = np.random.default_rng(seed)
    vocab = list(config.SEEDS) + [f"mot{i:05d}" for i in range(n_words - len(config.SEEDS))]
    E = rng.normal(size=(n_words, dim)).astype(np.float32)
    game = E + noise * rng.normal(size=E.shape).astype(np.float32)
    game /= np.linalg.norm(game, axis=1, keepdims=True)

    def score(guess: int, target: int) -> float:
        return float(100 * game[guess] @ game[target])

    return vocab, E, score


class FakeGameDevice:
    """Simule l'ecran de jeu : saisie, mots refuses, succes au Nieme essai, pub apres la victoire."""

    def __init__(self, vocab, score_fn, target, refuse=(), popup_at=None, ad_after_win=False,
                 broken=False, day="61"):
        self.vocab, self.score_fn, self.target = vocab, score_fn, vocab.index(target) if isinstance(target, str) else target
        self.refuse, self.popup_at, self.ad_after_win, self.broken, self.day = set(refuse), popup_at, ad_after_win, broken, day
        self.field = ""
        self.count = 0
        self.last = None            # (mot, score)
        self.won = False
        self.ad_open = False
        self.popup = False
        self.keyboard = True
        self.tried = []             # mots effectivement envoyes
        self.fg = config.APP_PACKAGE
        self.launched = 0
        self.dismissed_popups = 0

    # --- entrees -----------------------------------------------------------------------
    def foreground(self):
        return self.fg

    def launch(self, package, activity):
        self.fg = package
        self.launched += 1

    def type_text(self, text):
        self.field += text

    def key(self, name):
        if name == "KEYCODE_ENTER":
            self._enter()
        elif name == "KEYCODE_DEL":
            self.field = self.field[:-1]
        elif name == "KEYCODE_BACK":
            self.keyboard = False

    def tap(self, x, y):
        if self.ad_open and (x, y) == config.CLOSE_XY:
            self.ad_open = False
        elif self.popup and not self.keyboard and 1600 <= y <= 1700:     # bouton Continuer
            self.popup = False
            self.dismissed_popups += 1
        elif not self.popup and not self.ad_open:
            self.keyboard = True                                          # tap sur le champ

    def swipe(self, *a, **k):
        pass

    def _enter(self):
        word = self.field
        self.tried.append(word)
        known = {w for w in self.vocab}
        if word in self.refuse or word not in known:
            return                                                        # refuse : le champ reste rempli
        self.field = ""
        i = self.vocab.index(word)
        if i == self.target:
            self.won = True
            self.ad_open = self.ad_after_win
            return
        self.count += 1
        self.last = (word, self.score_fn(i, self.target))
        if self.popup_at and self.count == self.popup_at:
            self.popup = True

    # --- sortie ------------------------------------------------------------------------
    def screen(self) -> Screen:
        if self.ad_open:
            return screen_of("Test Ad", "Learn More")
        if self.popup:
            nodes = [("SUCCÈS DÉBLOQUÉ", "android.widget.TextView", (0, 0, 10, 10)),
                     ("Marathonien", "android.widget.TextView", (0, 0, 10, 10)),
                     ("Continuer", "android.widget.Button", (100, 1600, 980, 1700))]
            return Screen.from_xml(make_xml(nodes))
        if self.won:
            return screen_of("Historique") if self.ad_after_win else screen_of("Tu as trouvé le mot", "Terminer")
        if self.broken or self.last is None:                              # pas encore d'en-tete de resultat
            return screen_of("Archive", "Abandonner", f"Mot n° {self.day} du 27 septembre 2026",
                             edit=self.field or "Tape un mot…")
        word, sc = self.last
        return screen_of("Archive", "Abandonner", f"Mot n° {self.day} du 27 septembre 2026", word,
                         f"essai {self.count}", f"{sc:.2f}".replace(".", ","), edit=self.field or "Tape un mot…")


class ScriptedDevice:
    """Machine a etats : chaque etat = liste de (texte, bounds, etat_suivant) ; un tap sur un noeud change d'etat."""

    def __init__(self, states, start, close_to=None):
        self.states, self.state, self.close_to = states, start, close_to
        self.taps = []
        self.history = [start]

    def screen(self) -> Screen:
        nodes = [(t, "android.widget.EditText" if t.startswith("Tape") else "android.widget.TextView", b)
                 for t, b, _ in self.states[self.state]]
        return Screen.from_xml(make_xml(nodes))

    def tap(self, x, y):
        self.taps.append((x, y))
        if self.state == "ad" and (x, y) == config.CLOSE_XY:
            self._go(self.close_to)
            return
        for _, b, nxt in self.states[self.state]:
            if nxt and b[0] <= x <= b[2] and b[1] <= y <= b[3]:
                self._go(nxt)
                return

    def _go(self, nxt):
        self.state = nxt
        self.history.append(nxt)

    def foreground(self):
        return config.APP_PACKAGE

    def launch(self, package, activity):
        pass

    def swipe(self, *a, **k):
        pass

    def key(self, name):
        pass

    def type_text(self, text):
        pass
