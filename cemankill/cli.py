"""Ligne de commande : python -m cemankill --days N."""
import argparse
import os
import time

from . import config
from .device import AdbDevice
from .game import Player, SafetyAbort
from .navigation import open_next_archive
from .solver import Solver
from .storage import ObsStore


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="cemankill", description="Joue les archives de Cemanty sur un emulateur Android.")
    ap.add_argument("--days", type=int, default=1, help="nombre de jours d'archive a jouer")
    ap.add_argument("--max-guesses", type=int, default=250, help="plafond d'essais par mot")
    ap.add_argument("--resume", action="store_true", help="une partie est deja ouverte a l'ecran")
    ap.add_argument("--data-dir", default=config.DATA_DIR, help="dossier contenant emb.npy et vocab.txt")
    return ap


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    os.makedirs(args.data_dir, exist_ok=True)
    logf = open(os.path.join(args.data_dir, "bot.log"), "a", encoding="utf-8")

    def log(msg: str) -> None:
        print(msg, flush=True)
        logf.write(msg + "\n")
        logf.flush()

    player = Player(AdbDevice(), Solver.load(args.data_dir), ObsStore(os.path.join(args.data_dir, "obs.json")), log)
    try:
        for d in range(args.days):
            player.close_ads()
            if not (args.resume and d == 0) and not open_next_archive(player):
                log("!! impossible d'ouvrir la prochaine archive, arret")
                return 1
            t0 = time.time()
            n, word = player.play_word(args.max_guesses)
            if n is None:
                log(f"!! echec apres {args.max_guesses} essais")
                return 1
            log(f"OK  {word} trouve en {n} essais ({time.time() - t0:.0f}s)")
            if not player.leave_game():
                log("!! ecran de victoire non ferme (ni Terminer ni Fermer)")
    except SafetyAbort as exc:
        log(f"!! arret de securite : {exc}")
        return 1
    return 0
