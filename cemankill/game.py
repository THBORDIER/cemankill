"""Logique de jeu : jouer un mot jusqu'a la victoire, en gerant pubs, succes et mots refuses."""
import time
from typing import Callable, Optional, Tuple

from . import config
from .screen import GameState, parse_state
from .solver import Solver
from .storage import ObsStore
from .text import strip_accents


class Player:
    def __init__(self, device, solver: Solver, store: ObsStore, log: Callable[[str], None] = print,
                 sleep: Callable[[float], None] = time.sleep):
        self.dev, self.solver, self.store, self.log, self.sleep = device, solver, store, log, sleep

    # --- gestes de base -----------------------------------------------------------------
    def tap_text(self, text: str, last: bool = False, wait: float = 1.2) -> bool:
        node = self.dev.screen().find(text, last)
        if node is None:
            return False
        self.dev.tap(*node.center)
        self.sleep(wait)
        return True

    def focus_input(self) -> bool:
        node = self.dev.screen().edit_text()
        if node is None:
            return False
        self.dev.tap(*node.center)
        self.sleep(0.6)
        return True

    def clear_field(self, length: int) -> None:
        self.dev.key("KEYCODE_MOVE_END")
        for _ in range(length + 2):
            self.dev.key("KEYCODE_DEL")

    def leave_game(self) -> bool:
        """Ferme ce qui couvre l'ecran : victoire (« Terminer » mot bonus, « Fermer » archive), fenetre de jeton (« Plus tard »). Puis ferme la pub eventuelle."""
        left = any(self.tap_text(label, wait=2) for label in ("Terminer", "Fermer", "Plus tard"))
        self.close_ads()
        return left

    # --- publicites et succes -----------------------------------------------------------
    def ensure_app(self) -> bool:
        """Ramene Cemanty au premier plan si une pub a ouvert autre chose (navigateur, Play Store). On n'interagit jamais avec l'autre appli."""
        for _ in range(3):
            if self.dev.foreground() in (config.APP_PACKAGE, ""):
                return True
            self.log("  autre appli au premier plan -> retour")
            self.dev.key("KEYCODE_BACK")
            self.sleep(1)
        self.dev.launch(config.APP_PACKAGE, config.APP_ACTIVITY)
        self.sleep(3)
        return self.dev.foreground() in (config.APP_PACKAGE, "")

    def close_ads(self, limit: int = 90) -> bool:
        """Touche la croix des pubs jusqu'a ce qu'il n'y ait plus de pub. La croix n'apparait qu'apres 5-10 s."""
        closed = False
        for _ in range(limit):
            if not parse_state(self.dev.screen()).ad:
                return closed
            closed = True
            self.dev.tap(*config.CLOSE_XY)
            self.sleep(2)
            self.ensure_app()                          # un tap mal place peut ouvrir la page de l'annonceur
        self.log(f"!! pub encore ouverte apres {limit} essais")
        return closed

    def dismiss_achievement(self) -> bool:
        """Le bouton « Continuer » est sous le clavier : on masque le clavier, on clique, on refocalise le champ."""
        self.dev.key("KEYCODE_BACK")
        self.sleep(0.8)
        self.tap_text("Continuer", wait=1.0)
        self.focus_input()
        return True

    def settle(self) -> GameState:
        """Lit l'etat de l'ecran apres un envoi, en fermant d'abord pubs et succes eventuels."""
        state = parse_state(self.dev.screen())
        if state.ad:
            self.close_ads()
            state = parse_state(self.dev.screen())
        if state.achievement:
            self.dismiss_achievement()
            state = parse_state(self.dev.screen())
        return state

    # --- une partie ---------------------------------------------------------------------
    def submit(self, word: str) -> None:
        self.dev.type_text(strip_accents(word))
        self.dev.key("KEYCODE_ENTER")
        self.sleep(0.9)

    def play_word(self, max_guesses: int = 250) -> Tuple[Optional[int], Optional[str]]:
        """Joue jusqu'a la victoire. Renvoie (nombre d'essais, dernier mot) ou (None, None) en cas d'echec."""
        self.solver.reset()
        n = refused = stuck = 0
        day = None
        while n < max_guesses:
            if stuck > config.MAX_STUCK:
                self.log("!! bot bloque (aucune progression), arret")
                return None, None
            try:
                i = self.solver.next()
            except RuntimeError:                       # amorces epuisees sans avoir jamais lu un score
                self.log("!! aucun score lu a l'ecran et plus de mot d'amorce, arret")
                return None, None
            word = self.solver.vocab[i]
            self.submit(word)
            state = self.settle()
            if state.finished:
                return n + 1, word
            if state.field_dirty:                      # mot refuse : il reste dans le champ
                self.clear_field(len(state.field))
                self.solver.ban(i)
                refused += 1
                stuck += 1
                continue
            if state.last_word is None or state.last_score is None:
                stuck += 1
                self.sleep(1)
                continue
            stuck = 0
            n += 1
            day = day or state.day or "?"
            self.solver.add(i, state.last_score)
            self.store.save(day, [(self.solver.vocab[k], s) for k, s in self.solver.obs])
            if n % 10 == 0:
                k, s = max(self.solver.obs, key=lambda o: o[1])
                self.log(f"   essai {n}: meilleur {self.solver.vocab[k]} {s:.1f} (refuses {refused})")
        return None, None
