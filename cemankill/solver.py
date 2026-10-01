"""Solveur : regression a noyau (kernel ridge) sur embeddings centres. Pur numpy, sans adb ni Ollama."""
import os
from typing import List, Optional, Sequence

import numpy as np

from . import config
from .text import variants


class Solver:
    """Chaque score observe contraint la direction du mot cible dans l'espace des vecteurs."""

    def __init__(self, embeddings: np.ndarray, vocab: Sequence[str], seeds=config.SEEDS,
                 pool: int = config.POOL, lam: float = config.RIDGE_LAMBDA,
                 min_obs: int = config.MIN_OBS_BEFORE_MODEL):
        E = np.asarray(embeddings, dtype=np.float32)
        E = E - E.mean(0)                                    # centrage : sans lui tous les cosinus sont entre 0,4 et 0,8
        self.E = E / np.linalg.norm(E, axis=1, keepdims=True)
        self.vocab: List[str] = list(vocab)
        self.index = {w: i for i, w in enumerate(self.vocab)}
        self.seeds, self.pool, self.lam, self.min_obs = list(seeds), pool, lam, min_obs
        self.reset()

    @classmethod
    def load(cls, data_dir: str = config.DATA_DIR) -> "Solver":
        E = np.load(os.path.join(data_dir, "emb.npy"))
        with open(os.path.join(data_dir, "vocab.txt"), encoding="utf-8") as f:
            return cls(E, f.read().splitlines())

    def reset(self) -> None:
        self.obs: List[tuple] = []       # (indice du mot, score)
        # Cemanty refuse les locutions avec tiret (ex. « parle-lui ») : elles ne doivent jamais etre proposees.
        self.used: set = {i for i, word in enumerate(self.vocab) if "-" in word}
        self._seed_pos = 0

    def add(self, i: int, score: float) -> None:
        self.obs.append((i, score))
        self.used.add(i)
        for v in variants(self.vocab[i]):
            j = self.index.get(v)
            if j is not None:
                self.used.add(j)

    def ban(self, i: int) -> None:
        self.used.add(i)

    def next(self) -> int:
        if len(self.obs) < self.min_obs:
            seed = self._next_seed()
            if seed is not None:
                return seed
        if not self.obs:
            raise RuntimeError("aucune observation et plus de mot d'amorce")
        ids = [i for i, _ in self.obs]
        s = np.array([sc for _, sc in self.obs], dtype=np.float64) / 100.0
        G = self.E[ids].astype(np.float64)
        alpha = np.linalg.solve(G @ G.T + self.lam * np.eye(len(ids)), s - s.mean())
        pred = self.E[: self.pool] @ (G.T @ alpha).astype(np.float32)
        blocked = [i for i in self.used if i < self.pool]
        pred[blocked] = -np.inf
        return int(np.argmax(pred))

    def _next_seed(self) -> Optional[int]:
        while self._seed_pos < len(self.seeds):
            i = self.index.get(self.seeds[self._seed_pos])
            self._seed_pos += 1
            if i is not None and i not in self.used:
                return i
        return None
