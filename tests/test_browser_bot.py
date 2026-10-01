import numpy as np

from browser_bot.bot import WebBot
from browser_bot.browser import (
    RejectedWord,
    Submission,
    ad_detected,
    guest_limit_reached,
    is_pending_archive_label,
    is_safe_ad_close_label,
    is_allowed_url,
)
from browser_bot.state import WebState, parse_snapshot
from browser_bot.storage import RejectedStore
from cemankill import config
from cemankill.solver import Solver
from cemankill.storage import ObsStore


def test_parse_live_snapshot_ignores_scale_bingo():
    text = """Mot n° 65
DERNIER MOT · ESSAI 1
maison
-6,28
Glacial
1000
BINGO !
100,00
Tes essais
"""
    state = parse_snapshot(text)
    assert state == WebState("65", 1, "maison", -6.28, False)


def test_parse_victory_snapshot():
    state = parse_snapshot("Mot n° 65\nTu as trouvé « crépuscule » en 102 essais !")
    assert state.day == "65" and state.attempt == 102
    assert state.last_word == "crépuscule" and state.last_score == 100.0 and state.won


def test_parse_bonus_snapshot():
    state = parse_snapshot("Bonus du jour\nAbandonner\nphotosynthèse\nessai 26\n100,00\nTrouvé")
    assert state == WebState("bonus", 26, "photosynthèse", 100.0, True)


def test_url_guard_accepts_only_cemanty_https():
    assert is_allowed_url("https://cemanty.fr/jouer/")
    assert is_allowed_url("https://www.cemanty.fr/jouer/")
    assert not is_allowed_url("http://cemanty.fr/jouer/")
    assert not is_allowed_url("https://cemanty.fr.example.com/")
    assert not is_allowed_url("https://cemanty.fr/")
    assert not is_allowed_url("https://cemanty.fr/profil/")
    assert not is_allowed_url("https://play.google.com/store/apps/details?id=x")


def test_ad_detection_uses_visible_ad_markers():
    assert ad_detected("Test Ad\nyoutube.com\nLearn More")
    assert ad_detected("Ad 1 of 2")
    assert not ad_detected("Mot n° 65\nTape un mot…")


def test_guest_limit_is_distinct_from_the_initial_account_nag():
    assert guest_limit_reached(
        "Tes essais en invité sont passés\nCrée un compte pour continuer le mot du jour"
    )
    assert not guest_limit_reached("Tu joues en invité\nCrée un compte !\nPlus tard")


def test_pending_archive_is_identified_without_using_completed_rows():
    assert is_pending_archive_label("22\nMot à trouver\nPas joué · encore jouable\nÀ jouer")
    assert not is_pending_archive_label(
        "23\ncrépuscule\nhistorique\nPas joué ce jour-là · trouvé après coup\n102 essais"
    )


def test_rewarded_ad_closer_refuses_ad_content_actions():
    assert is_safe_ad_close_label("Fermer la publicité")
    assert is_safe_ad_close_label("Close ad")
    assert not is_safe_ad_close_label("Learn More")
    assert not is_safe_ad_close_label("Installer")
    assert not is_safe_ad_close_label("Regarder")


class FakeWebSession:
    def __init__(self, vocab, target, scores, rejected=(), initial=None):
        self.vocab = vocab
        self.target = target
        self.scores = scores
        self.rejected = set(rejected)
        self.tried = []
        self.initial = initial

    def prepare_game(self):
        if self.initial:
            return WebState("65", 1, self.initial, self.scores[self.initial], False)
        return WebState(day="65")

    def submit(self, word):
        self.tried.append(word)
        if word in self.rejected:
            raise RejectedWord(word)
        attempt = len(self.tried)
        won = word == self.target
        return Submission(word, 100.0 if won else self.scores[word], attempt, won)


def small_solver():
    vocab = list(config.SEEDS)
    embeddings = np.random.default_rng(2).normal(size=(len(vocab), 12)).astype(np.float32)
    scores = {word: float(i) for i, word in enumerate(vocab)}
    return vocab, Solver(embeddings, vocab), scores


def test_web_bot_reuses_solver_and_saves_observations(tmp_path):
    vocab, solver, scores = small_solver()
    session = FakeWebSession(vocab, "eau", scores)
    store = ObsStore(str(tmp_path / "web_obs.json"))
    attempts, word = WebBot(session, solver, store, lambda message: None).play(10)
    assert (attempts, word) == (3, "eau")
    assert [item[0] for item in store.load()["65"]] == ["maison", "animal", "eau"]


def test_web_bot_bans_rejected_word(tmp_path):
    vocab, solver, scores = small_solver()
    session = FakeWebSession(vocab, "animal", scores, rejected={"maison"})
    attempts, word = WebBot(
        session, solver, ObsStore(str(tmp_path / "web_obs.json")), lambda message: None
    ).play(5)
    assert word == "animal" and session.tried == ["maison", "animal"]


def test_web_bot_restores_last_visible_result(tmp_path):
    vocab, solver, scores = small_solver()
    session = FakeWebSession(vocab, "animal", scores, initial="maison")
    attempts, word = WebBot(
        session, solver, ObsStore(str(tmp_path / "web_obs.json")), lambda message: None
    ).play(3)
    assert word == "animal" and session.tried == ["animal"]


def test_web_bot_persists_and_restores_rejected_words(tmp_path):
    vocab, solver, scores = small_solver()
    rejected_store = RejectedStore(str(tmp_path / "web_banned.json"))
    session = FakeWebSession(vocab, "animal", scores, rejected={"maison"})
    attempts, word = WebBot(
        session,
        solver,
        ObsStore(str(tmp_path / "web_obs.json")),
        lambda message: None,
        rejected_store,
    ).play(5)
    assert word == "animal" and rejected_store.load("65") == {"maison"}

    _, next_solver, scores = small_solver()
    resumed = FakeWebSession(vocab, "animal", scores, rejected={"maison"})
    WebBot(
        resumed,
        next_solver,
        ObsStore(str(tmp_path / "other_obs.json")),
        lambda message: None,
        rejected_store,
    ).play(5)
    assert resumed.tried == ["animal"]
