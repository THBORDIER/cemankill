"""Tests de la boucle de jeu et de la navigation avec de faux appareils (aucun adb, aucun Android)."""
import pytest

from cemankill import config
from cemankill.game import Player, SafetyAbort
from cemankill.navigation import open_next_archive
from cemankill.solver import Solver
from cemankill.storage import ObsStore
from tests.fakes import FakeGameDevice, ScriptedDevice, make_world


@pytest.fixture
def world():
    return make_world(seed=3)


def make_player(world, tmp_path, target, **kw):
    vocab, E, score = world
    dev = FakeGameDevice(vocab, score, target, **kw)
    logs = []
    p = Player(dev, Solver(E, vocab), ObsStore(str(tmp_path / "obs.json")), logs.append, sleep=lambda s: None)
    return p, dev, logs


def test_plays_until_victory_and_records_scores(world, tmp_path):
    p, dev, _ = make_player(world, tmp_path, target=700)
    n, word = p.play_word(200)
    assert word == dev.vocab[700] and n == dev.count + 1 <= 200
    saved = ObsStore(str(tmp_path / "obs.json")).load()["61"]
    assert len(saved) == dev.count and all(len(x) == 2 for x in saved)


def test_refused_word_is_cleared_and_never_retried(world, tmp_path):
    first_seed = config.SEEDS[0]
    p, dev, _ = make_player(world, tmp_path, target=900, refuse={first_seed})
    n, word = p.play_word(200)
    assert word == dev.vocab[900]
    assert dev.tried.count(first_seed) == 1                      # essaye une fois, refuse, jamais reessaye
    assert not any(first_seed in t and t != first_seed for t in dev.tried)   # pas de mots accoles dans le champ
    assert dev.field == ""


def test_achievement_popup_behind_keyboard_is_dismissed(world, tmp_path):
    p, dev, _ = make_player(world, tmp_path, target=1200, popup_at=7)
    n, word = p.play_word(200)
    assert word == dev.vocab[1200]
    assert dev.dismissed_popups == 1 and not dev.popup


def test_ad_after_victory_is_closed_and_game_reported_finished(world, tmp_path):
    p, dev, _ = make_player(world, tmp_path, target=500, ad_after_win=True)
    n, word = p.play_word(200)
    assert word == dev.vocab[500] and not dev.ad_open


def test_gives_up_when_screen_never_shows_progress(world, tmp_path):
    p, dev, logs = make_player(world, tmp_path, target=500, broken=True)
    assert p.play_word(200) == (None, None)
    assert any(m.startswith("!!") for m in logs)                   # arret explique, pas d'exception
    assert len(dev.tried) <= config.MAX_STUCK + 3                 # s'arrete vite au lieu de taper indefiniment


def test_respects_max_guesses(world, tmp_path):
    p, dev, _ = make_player(world, tmp_path, target=1999)
    assert p.play_word(5) == (None, None) and dev.count == 5


def test_accents_are_stripped_when_typing(tmp_path):
    vocab, E, score = make_world(n_words=400)
    vocab[30] = "hélicoptère"
    fake_vocab = list(vocab)
    fake_vocab[30] = "helicoptere"                                 # le jeu connait la forme sans accent
    dev = FakeGameDevice(fake_vocab, score, 5)
    p = Player(dev, Solver(E, vocab), ObsStore(str(tmp_path / "o.json")), lambda m: None, sleep=lambda s: None)
    p.submit("hélicoptère")
    assert dev.tried == ["helicoptere"]


def test_close_ads_taps_until_gone_and_reports(world, tmp_path):
    class Dev(FakeGameDevice):
        closes_needed = 3
        def tap(self, x, y):
            if (x, y) == config.CLOSE_XY:
                self.closes_needed -= 1
                self.ad_open = self.closes_needed > 0
    vocab, E, score = world
    dev = Dev(vocab, score, 5)
    dev.ad_open = True
    p = Player(dev, Solver(E, vocab), ObsStore(str(tmp_path / "o.json")), lambda m: None, sleep=lambda s: None)
    assert p.close_ads() is True and not dev.ad_open and dev.closes_needed == 0
    assert p.close_ads() is False                                  # rien a fermer


def test_close_ads_gives_up_after_limit(world, tmp_path):
    vocab, E, score = world
    dev = FakeGameDevice(vocab, score, 5)
    dev.ad_open = True
    dev.tap = lambda x, y: None                                    # la croix ne repond jamais
    logs = []
    p = Player(dev, Solver(E, vocab), ObsStore(str(tmp_path / "o.json")), logs.append, sleep=lambda s: None)
    p.close_ads(limit=4)
    assert any("pub encore ouverte" in m for m in logs)


# --- navigation -----------------------------------------------------------------------
def nav_states(with_token):
    tab = ("Historique", (0, 2100, 300, 2300), "history")
    sheet_btn = ("Jouer ce mot · 1 jeton", (0, 2000, 1080, 2100), "game" if with_token else "no_token")
    return {
        "home": [("Jouer", (0, 2100, 100, 2300), None), tab],
        "history": [("Historique", (0, 100, 500, 200), None), ("Mot à trouver", (0, 800, 1080, 900), "sheet"), tab],
        "sheet": [sheet_btn],
        "no_token": [("Regarder une pub", (0, 1900, 1080, 2000), "ad")],
        "ad": [("Test Ad", (0, 0, 10, 10), None)],
        "pending": [("Ton jeton arrive… Réessaie dans un instant.", (0, 1700, 1080, 1800), None),
                    ("Vérifier", (0, 1850, 1080, 1950), "after_ad")],
        "after_ad": [("Jouer ce mot · 1 jeton", (0, 2000, 1080, 2100), "game")],
        "game": [("Abandonner", (0, 0, 10, 10), None), ("Tape un mot…", (0, 2200, 1080, 2300), None)],
    }


def nav_player(dev):
    p = Player(dev, None, None, lambda m: None, sleep=lambda s: None)
    return p


def test_open_next_archive_with_token():
    dev = ScriptedDevice(nav_states(True), "home")
    assert open_next_archive(nav_player(dev)) is True
    assert dev.history[:4] == ["home", "history", "sheet", "game"]


def test_open_next_archive_watches_ad_when_out_of_tokens():
    dev = ScriptedDevice(nav_states(False), "home", close_to="pending")
    assert open_next_archive(nav_player(dev)) is True
    assert dev.history == ["home", "history", "sheet", "no_token", "ad", "pending", "after_ad", "game"]
    assert config.CLOSE_XY in dev.taps


def test_open_next_archive_fails_cleanly_when_nothing_to_play():
    states = nav_states(True)
    states["history"] = [s for s in states["history"] if s[0] != "Mot à trouver"]
    dev = ScriptedDevice(states, "home")
    assert open_next_archive(nav_player(dev), scrolls=3) is False


# --- fin de partie : Terminer (mot bonus) ou Fermer (archive) ---------------------------
@pytest.mark.parametrize("label", ["Terminer", "Fermer"])
def test_leave_game_closes_victory_screen_whatever_its_button(label):
    states = {
        "victory": [("Tu as trouvé « médicament » en 58 essais !", (0, 500, 1080, 600), None), (label, (0, 2000, 1080, 2100), "history")],
        "history": [("Historique", (0, 2100, 300, 2300), None)],
    }
    dev = ScriptedDevice(states, "victory")
    assert nav_player(dev).leave_game() is True
    assert dev.state == "history"


def test_leave_game_reports_failure_when_no_button():
    dev = ScriptedDevice({"victory": [("Tu as trouvé le mot", (0, 0, 10, 10), None)]}, "victory")
    assert nav_player(dev).leave_game() is False


def test_open_next_archive_recovers_from_victory_sheet_hiding_the_tabs():
    states = nav_states(True)
    states["victory"] = [("Tu as trouvé « médicament » en 58 essais !", (0, 500, 1080, 600), None),
                         ("Fermer", (0, 2000, 1080, 2100), "home")]
    dev = ScriptedDevice(states, "victory")
    assert open_next_archive(nav_player(dev)) is True
    assert dev.history[:5] == ["victory", "home", "history", "sheet", "game"]


# --- une pub qui ouvre une autre appli ----------------------------------------------------
def test_ensure_app_returns_immediately_with_back(world, tmp_path):
    vocab, E, score = world
    dev = FakeGameDevice(vocab, score, 5)
    dev.fg = "com.android.chrome"
    backs = []
    def back(name):
        backs.append(name)
        if name == "KEYCODE_BACK":
            dev.fg = config.APP_PACKAGE
    dev.key = back
    p = Player(dev, Solver(E, vocab), ObsStore(str(tmp_path / "o.json")), lambda m: None, sleep=lambda s: None)
    assert p.ensure_app() is True
    assert backs == ["KEYCODE_BACK"] and dev.launched == 0 and dev.fg == config.APP_PACKAGE


def test_ensure_app_does_nothing_when_app_is_in_front(world, tmp_path):
    vocab, E, score = world
    dev = FakeGameDevice(vocab, score, 5)
    p = Player(dev, Solver(E, vocab), ObsStore(str(tmp_path / "o.json")), lambda m: None, sleep=lambda s: None)
    assert p.ensure_app() is True and dev.launched == 0


def test_ensure_app_stops_if_external_page_cannot_be_left(world, tmp_path):
    vocab, E, score = world
    dev = FakeGameDevice(vocab, score, 5)
    dev.fg = "com.android.vending"
    backs = []
    dev.key = backs.append
    p = Player(dev, Solver(E, vocab), ObsStore(str(tmp_path / "o.json")), lambda m: None, sleep=lambda s: None)
    with pytest.raises(SafetyAbort, match="impossible de quitter"):
        p.ensure_app()
    assert backs == ["KEYCODE_BACK"] * 3 and dev.launched == 0


def test_ensure_app_stops_without_click_when_foreground_is_unknown(world, tmp_path):
    vocab, E, score = world
    dev = FakeGameDevice(vocab, score, 5)
    dev.fg = ""
    keys = []
    dev.key = keys.append
    p = Player(dev, Solver(E, vocab), ObsStore(str(tmp_path / "o.json")), lambda m: None, sleep=lambda s: None)
    with pytest.raises(SafetyAbort, match="inconnue"):
        p.ensure_app()
    assert keys == [] and dev.launched == 0


def test_close_ads_recovers_when_croix_tap_opens_advertiser_page(world, tmp_path):
    vocab, E, score = world
    dev = FakeGameDevice(vocab, score, 5)
    dev.ad_open = True
    def tap(x, y):
        dev.ad_open = False
        dev.fg = "com.android.chrome"                             # le tap est tombe sur l'annonce : Chrome s'ouvre
    dev.tap = tap
    dev.key = lambda name: setattr(dev, "fg", config.APP_PACKAGE) if name == "KEYCODE_BACK" else None
    p = Player(dev, Solver(E, vocab), ObsStore(str(tmp_path / "o.json")), lambda m: None, sleep=lambda s: None)
    assert p.close_ads() is True
    assert dev.fg == config.APP_PACKAGE


def test_open_next_archive_gives_up_if_token_is_never_credited():
    states = nav_states(False)
    states["pending"] = [("Ton jeton arrive… Réessaie dans un instant.", (0, 1700, 1080, 1800), None),
                         ("Vérifier", (0, 1850, 1080, 1950), "pending")]      # « Vérifier » ne change jamais rien
    dev = ScriptedDevice(states, "home", close_to="pending")
    logs = []
    p = Player(dev, None, None, logs.append, sleep=lambda s: None)
    assert open_next_archive(p) is False
    assert any("jeton non credite" in m for m in logs)


@pytest.mark.parametrize("button", ["Plus tard", "Fermer", "Terminer"])
def test_open_next_archive_recovers_from_any_covering_sheet(button):
    states = nav_states(True)
    states["stale"] = [("Ce mot te coûte un jeton", (0, 500, 1080, 600), None), (button, (0, 2200, 1080, 2300), "home")]
    dev = ScriptedDevice(states, "stale")
    assert open_next_archive(nav_player(dev)) is True
    assert dev.history[:3] == ["stale", "home", "history"]


def test_open_next_archive_reports_when_tab_bar_is_unreachable():
    dev = ScriptedDevice({"stuck": [("Ecran inconnu", (0, 0, 10, 10), None)]}, "stuck")
    logs = []
    p = Player(dev, None, None, logs.append, sleep=lambda s: None)
    assert open_next_archive(p) is False and any("Historique introuvable" in m for m in logs)
