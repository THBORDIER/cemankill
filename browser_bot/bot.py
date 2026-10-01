"""Boucle de jeu du bot web, independante de Playwright."""
from datetime import date
from typing import Callable, Optional, Tuple

from cemankill import config
from cemankill.solver import Solver
from cemankill.storage import ObsStore

from .browser import RejectedWord


class WebBot:
    def __init__(self, session, solver: Solver, store: ObsStore, log: Callable[[str], None] = print,
                 rejected_store=None):
        self.session = session
        self.solver = solver
        self.store = store
        self.log = log
        self.rejected_store = rejected_store

    def _restore(self, day: str) -> None:
        for word, score in self.store.load().get(str(day), []):
            index = self.solver.index.get(word)
            if index is not None and index not in self.solver.used:
                self.solver.add(index, float(score))

    def play(self, max_guesses: int = 250) -> Tuple[Optional[int], Optional[str]]:
        state = self.session.prepare_game()
        if state.won:
            return state.attempt, state.last_word
        day = f"bonus-{date.today().isoformat()}" if state.day == "bonus" else (state.day or "web")
        self.solver.reset()
        self._restore(day)
        if self.rejected_store is not None:
            for word in self.rejected_store.load(day):
                index = self.solver.index.get(word)
                if index is not None:
                    self.solver.ban(index)
        if state.last_word is not None and state.last_score is not None:
            previous = self.solver.index.get(state.last_word)
            if previous is not None and previous not in self.solver.used:
                self.solver.add(previous, state.last_score)
                self.store.save(day, [(self.solver.vocab[i], score) for i, score in self.solver.obs])
        refused = accepted = 0

        while accepted < max_guesses:
            if refused > max(max_guesses, config.MAX_STUCK * 4):
                self.log("!! trop de mots refuses, arret")
                return None, None
            try:
                index = self.solver.next()
            except RuntimeError:
                self.log("!! plus aucun mot exploitable")
                return None, None
            word = self.solver.vocab[index]
            try:
                result = self.session.submit(word)
            except RejectedWord:
                self.solver.ban(index)
                refused += 1
                if self.rejected_store is not None:
                    self.rejected_store.add(day, word)
                if refused <= 5 or refused % 10 == 0:
                    self.log(f"   refuse {refused}: {word}")
                continue

            accepted += 1
            self.solver.add(index, result.score)
            self.store.save(day, [(self.solver.vocab[i], score) for i, score in self.solver.obs])
            if result.won:
                return result.attempt or len(self.solver.obs), word
            if len(self.solver.obs) % 10 == 0:
                best_i, best_score = max(self.solver.obs, key=lambda item: item[1])
                self.log(
                    f"   essai {result.attempt or len(self.solver.obs)}: meilleur "
                    f"{self.solver.vocab[best_i]} {best_score:.2f} (refuses {refused})"
                )
        return None, None
