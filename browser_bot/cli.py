"""Commande : python -m browser_bot."""
import argparse
import os
import time

from cemankill import config
from cemankill.solver import Solver
from cemankill.storage import ObsStore

from .bot import WebBot
from .browser import (
    ArchiveTokenUnavailable,
    BrowserBotError,
    BrowserSafetyError,
    BrowserSession,
    DEFAULT_URL,
)
from .storage import RejectedStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="browser_bot", description="Joue le mot quotidien de Cemanty dans un navigateur dedie.")
    parser.add_argument("--max-guesses", type=int, default=250, help="nombre maximal de nouveaux essais")
    parser.add_argument("--data-dir", default=config.DATA_DIR, help="dossier contenant emb.npy et vocab.txt")
    parser.add_argument("--profile-dir", default=os.path.join(config.DATA_DIR, "browser-profile"),
                        help="profil navigateur dedie au bot")
    parser.add_argument("--browser", choices=("msedge", "chrome", "chromium"), default="msedge",
                        help="navigateur Playwright (msedge utilise Edge deja installe sous Windows)")
    parser.add_argument("--headless", action="store_true", help="masque la fenetre du navigateur")
    parser.add_argument("--check", action="store_true", help="ouvre et valide le plateau sans proposer de mot")
    parser.add_argument("--all-sessions", action="store_true",
                        help="joue aussi le mot bonus gratuit, sans archive, duel ni publicite")
    parser.add_argument("--watch", action="store_true",
                        help="reste en veille sur le compte a rebours et joue les prochains mots")
    parser.add_argument("--archives", action="store_true",
                        help="joue tous les jours manques disponibles depuis l'historique")
    parser.add_argument("--poll-seconds", type=float, default=30.0, help=argparse.SUPPRESS)
    parser.add_argument("--url", default=DEFAULT_URL, help=argparse.SUPPRESS)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    os.makedirs(args.data_dir, exist_ok=True)
    log_path = os.path.join(args.data_dir, "browser_bot.log")
    with open(log_path, "a", encoding="utf-8") as log_file:
        def log(message: str) -> None:
            print(message, flush=True)
            log_file.write(message + "\n")
            log_file.flush()

        try:
            with BrowserSession.open(args.profile_dir, args.browser, args.headless) as session:
                def make_bot():
                    return WebBot(
                        session,
                        Solver.load(args.data_dir),
                        ObsStore(os.path.join(args.data_dir, "web_obs.json")),
                        log,
                        rejected_store=RejectedStore(os.path.join(args.data_dir, "web_banned.json")),
                    )

                while args.archives:
                    try:
                        archive_state = session.start_next_archive(log)
                    except ArchiveTokenUnavailable as exc:
                        log(f".. archives en attente : {exc}")
                        if not args.watch:
                            return 2
                        session.page.wait_for_timeout(60 * 1000)
                        continue
                    except BrowserSafetyError:
                        raise
                    except BrowserBotError as exc:
                        if not args.watch:
                            raise
                        log(f".. incident transitoire dans les archives : {exc}; nouvelle tentative dans 15 s")
                        session.page.wait_for_timeout(15 * 1000)
                        continue
                    if archive_state is None:
                        log("OK  aucune archive jouable restante")
                        break
                    log(f".. résolution de l'archive, mot n° {archive_state.day or '?'}")
                    started = time.time()
                    archive_attempts, archive_word = make_bot().play(args.max_guesses)
                    if archive_attempts is None:
                        log(f"!! echec de l'archive après {args.max_guesses} nouveaux essais")
                        return 1
                    log(
                        f"OK  archive {archive_word} trouvée à l'essai {archive_attempts} "
                        f"({time.time() - started:.1f}s)"
                    )
                    session.finish_result()

                while True:
                    if args.watch:
                        log(".. veille : attente d'un nouveau plateau jouable")
                        state = session.wait_for_game(args.url, args.poll_seconds)
                    else:
                        state = session.prepare_game(args.url)
                    if args.check:
                        log(f"OK  plateau web pret, mot n° {state.day or '?'}")
                        return 0
                    bot = make_bot()
                    started = time.time()
                    attempts, word = bot.play(args.max_guesses)
                    if attempts is None:
                        log(f"!! echec apres {args.max_guesses} nouveaux essais")
                        return 1
                    log(f"OK  {word} trouve a l'essai {attempts} ({time.time() - started:.1f}s)")
                    if args.all_sessions and session.open_bonus():
                        bonus_bot = make_bot()
                        bonus_attempts, bonus_word = bonus_bot.play(args.max_guesses)
                        if bonus_attempts is None:
                            log(f"!! echec du mot bonus apres {args.max_guesses} nouveaux essais")
                            return 1
                        session.finish_result()
                        log(f"OK  bonus {bonus_word} trouve a l'essai {bonus_attempts}")
                    elif args.all_sessions:
                        log("OK  aucune partie bonus gratuite restante")
                    elif args.watch:
                        session.finish_result()
                    if not args.watch:
                        return 0
        except (BrowserBotError, OSError, ValueError) as exc:
            log(f"!! arret du bot web : {exc}")
            return 1
        except Exception as exc:
            detail = str(exc).splitlines()[0] if str(exc) else type(exc).__name__
            log(f"!! erreur navigateur : {detail}")
            return 1
