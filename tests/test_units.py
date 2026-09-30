"""Tests des briques pures : texte, ecran, stockage, ligne de commande."""
import json
import os

import pytest

from cemankill.cli import build_parser
from cemankill.screen import Screen, parse_score, parse_state
from cemankill.storage import ObsStore
from cemankill.text import strip_accents, variants
from tests.fakes import make_xml, screen_of


# --- text -----------------------------------------------------------------------------
def test_strip_accents():
    assert strip_accents("hélicoptère") == "helicoptere"
    assert strip_accents("œuf") == "œuf"            # ligature : non decomposable, laissee telle quelle
    assert strip_accents("maison") == "maison"


def test_variants_plural_and_feminine():
    assert {"animaux", "animals"} <= variants("animal")
    assert "chat" in variants("chats")
    assert "maisons" in variants("maison") and "maison" not in variants("maison")
    assert "grand" in variants("grande") or "grande" not in variants("grande")   # jamais le mot lui-meme
    assert "belle" not in variants("belle")


# --- screen ---------------------------------------------------------------------------
def test_parse_score_variants():
    assert parse_score("26,27") == 26.27
    assert parse_score("−2,16") == -2.16            # signe moins typographique
    assert parse_score("-0,14") == -0.14
    assert parse_score("très froid") is None
    assert parse_score(None) is None


def test_from_xml_reads_text_desc_and_bounds():
    xml = ('<hierarchy><node text="eau" class="a" bounds="[0,10][100,50]"/>'
           '<node text="" content-desc="0 jetons" class="b" bounds="[1,1][3,3]"/></hierarchy>')
    s = Screen.from_xml(xml)
    assert s.has("eau") and s.has("jetons")
    assert s.find("eau").center == (50, 30)


def test_from_xml_broken_is_empty_not_crash():
    assert Screen.from_xml("<hierarchy><node").texts == []
    assert Screen.from_xml("").nodes == []


def test_noise_fragments_are_ignored_but_words_kept():
    s = screen_of("voiture", "1000", "/1000", "582")
    assert s.texts == ["voiture", "582"]


def test_find_last_picks_bottom_tab():
    s = screen_of("Historique", "Jouer", "Historique")
    assert s.find("Historique", last=True) is s.nodes[2]
    assert s.find("Absent") is None


def test_parse_state_game_header():
    st = parse_state(screen_of("Archive", "Abandonner", "Mot n° 61 du 27 septembre 2026", "plante", "essai 31",
                               "29,62", "Froid", edit="Tape un mot…"))
    assert (st.day, st.last_word, st.last_score) == ("61", "plante", 29.62)
    assert st.in_game and not st.finished and not st.field_dirty


def test_parse_state_before_first_guess_has_no_result():
    st = parse_state(screen_of("Archive", "Abandonner", "Mot n° 61 du 27 septembre 2026", edit="Tape un mot…"))
    assert st.last_word is None and st.last_score is None and not st.finished


def test_parse_state_refused_word_leaves_field_dirty():
    st = parse_state(screen_of("Archive", "Abandonner", "Mot n° 61 du 27 septembre 2026", edit="forest"))
    assert st.field_dirty


@pytest.mark.parametrize("texts", [("Tu as trouvé « toxine » en 119 essais", "Voir le top 1000"), ("Terminer",)])
def test_parse_state_victory_screens(texts):
    assert parse_state(screen_of(*texts)).finished


def test_parse_state_left_the_game_is_finished():
    assert parse_state(screen_of("Historique", "Septembre 2026")).finished


def test_parse_state_ad_and_achievement_are_not_finished():
    ad = parse_state(screen_of("Test Ad", "Learn More"))
    ach = parse_state(screen_of("SUCCÈS DÉBLOQUÉ", "Marathonien", "Continuer"))
    assert ad.ad and not ad.finished
    assert ach.achievement and not ach.finished


# --- storage --------------------------------------------------------------------------
def test_store_roundtrip_and_merge(tmp_path):
    st = ObsStore(str(tmp_path / "sub" / "obs.json"))
    st.save(61, [("eau", 23.6), ("plante", 29.62)])
    st.save(60, [("animal", 17.9)])
    data = st.load()
    assert data["61"] == [["eau", 23.6], ["plante", 29.62]] and data["60"] == [["animal", 17.9]]
    assert not os.path.exists(st.path + ".tmp")


def test_store_overwrites_same_day_and_survives_corrupt_file(tmp_path):
    p = tmp_path / "obs.json"
    p.write_text("{pas du json", encoding="utf-8")
    st = ObsStore(str(p))
    assert st.load() == {}
    st.save(61, [("eau", 1.0)])
    st.save(61, [("eau", 1.0), ("feu", 2.0)])
    assert len(json.loads(p.read_text(encoding="utf-8"))["61"]) == 2


# --- cli ------------------------------------------------------------------------------
def test_cli_defaults_and_flags():
    a = build_parser().parse_args([])
    assert (a.days, a.max_guesses, a.resume) == (1, 250, False)
    a = build_parser().parse_args(["--days", "3", "--resume", "--max-guesses", "80"])
    assert (a.days, a.max_guesses, a.resume) == (3, 80, True)


def test_make_xml_helper_is_parseable():
    assert Screen.from_xml(make_xml([("x", "c", (0, 0, 1, 1))])).has("x")
