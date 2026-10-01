"""Tests du solveur sur un monde synthetique : le 'jeu' utilise des vecteurs differents de ceux du solveur."""
import numpy as np
import pytest

from cemankill import config
from cemankill.solver import Solver
from tests.fakes import make_world


def solve(target, vocab, E, score, limit=150):
    s = Solver(E, vocab)
    for n in range(1, limit + 1):
        i = s.next()
        assert i not in s.used                      # ne repropose jamais un mot deja essaye
        if i == target:
            return n
        s.add(i, score(i, target))
    return None


def test_seeds_come_first_in_order():
    vocab, E, _ = make_world()
    s = Solver(E, vocab)
    first = []
    for _ in range(config.MIN_OBS_BEFORE_MODEL):
        i = s.next()
        first.append(vocab[i])
        s.add(i, 0.0)
    assert first == config.SEEDS[: config.MIN_OBS_BEFORE_MODEL]


def test_finds_planted_targets_despite_model_mismatch():
    """Le modele du jeu n'est pas celui du solveur (bruit 0,35) : on exige de retrouver la cible dans la grande majorite des cas."""
    vocab, E, score = make_world(seed=1)
    rng = np.random.default_rng(42)
    targets = rng.choice(np.arange(len(config.SEEDS), 1500), size=12, replace=False)
    results = [solve(int(t), vocab, E, score) for t in targets]
    solved = [r for r in results if r]
    assert len(solved) >= 10, f"trop d'echecs : {results}"
    assert float(np.median(solved)) <= 80, f"trop lent : {results}"


def test_add_blocks_inflections():
    vocab = list(config.SEEDS) + ["cheval", "chevaux", "chevals", "chat", "chats", "zzz"]
    E = np.random.default_rng(0).normal(size=(len(vocab), 8)).astype(np.float32)
    s = Solver(E, vocab)
    s.add(vocab.index("chat"), 10.0)
    s.add(vocab.index("cheval"), 10.0)
    for blocked in ("chats", "chevaux", "chevals"):
        assert vocab.index(blocked) in s.used


def test_ban_excludes_word_from_proposals():
    vocab, E, score = make_world()
    s = Solver(E, vocab, min_obs=0)
    s.add(0, 10.0)
    s.add(1, 20.0)
    first = s.next()
    s.ban(first)
    assert s.next() != first


def test_hyphenated_words_are_never_candidates():
    vocab = list(config.SEEDS) + ["parle-lui", "arc-en-ciel", "motvalide"]
    E = np.random.default_rng(0).normal(size=(len(vocab), 8)).astype(np.float32)
    s = Solver(E, vocab, min_obs=0)
    assert vocab.index("parle-lui") in s.used
    assert vocab.index("arc-en-ciel") in s.used
    s.add(vocab.index("maison"), 10.0)
    assert s.next() not in {vocab.index("parle-lui"), vocab.index("arc-en-ciel")}


def test_reset_forgets_everything():
    vocab, E, _ = make_world()
    s = Solver(E, vocab)
    s.add(3, 5.0)
    s.reset()
    assert s.obs == [] and s.used == set() and vocab[s.next()] == config.SEEDS[0]


def test_next_without_observation_or_seed_raises():
    vocab, E, _ = make_world()
    s = Solver(E, vocab, seeds=[])
    with pytest.raises(RuntimeError):
        s.next()


def test_pool_limits_candidates_to_frequent_words():
    vocab, E, score = make_world()
    s = Solver(E, vocab, pool=500, min_obs=0)
    for i in range(3):
        s.add(i, float(10 * i))
    assert s.next() < 500


def test_load_roundtrip(tmp_path):
    vocab, E, _ = make_world(n_words=300)
    np.save(tmp_path / "emb.npy", E)
    (tmp_path / "vocab.txt").write_text("\n".join(vocab), encoding="utf-8")
    s = Solver.load(str(tmp_path))
    assert s.vocab == vocab and s.E.shape == E.shape
    assert np.allclose(np.linalg.norm(s.E, axis=1), 1.0, atol=1e-5)
