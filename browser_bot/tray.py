"""Controle Windows du bot depuis la zone de notification."""
from __future__ import annotations

import argparse
import ctypes
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

from PIL import Image

from .icon import create_icon


CREATE_NO_WINDOW = 0x08000000
ERROR_ALREADY_EXISTS = 183
MUTEX_NAME = "Local\\CemantyBrowserBotTray"


class FILETIME(ctypes.Structure):
    _fields_ = [("low", ctypes.c_ulong), ("high", ctypes.c_ulong)]


def build_bot_command(
    root: Path,
    executable: str | None = None,
    *,
    headless: bool = True,
) -> list[str]:
    command = [
        executable or sys.executable,
        "-m",
        "browser_bot",
        "--profile-dir",
        str(root / "data" / "account-profile"),
        "--all-sessions",
        "--archives",
        "--watch",
    ]
    if headless:
        command.append("--headless")
    return command


def process_is_running(pid: int) -> bool:
    if pid <= 0:
        return False
    process = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
    if not process:
        return False
    try:
        exit_code = ctypes.c_ulong()
        return bool(
            ctypes.windll.kernel32.GetExitCodeProcess(process, ctypes.byref(exit_code))
            and exit_code.value == 259
        )
    finally:
        ctypes.windll.kernel32.CloseHandle(process)


def process_creation_time(pid: int) -> int | None:
    """Retourne l'identite temporelle Windows d'un PID, ou None s'il a disparu."""
    if pid <= 0:
        return None
    process = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
    if not process:
        return None
    try:
        creation = FILETIME()
        exit_time = FILETIME()
        kernel = FILETIME()
        user = FILETIME()
        if not ctypes.windll.kernel32.GetProcessTimes(
            process,
            ctypes.byref(creation),
            ctypes.byref(exit_time),
            ctypes.byref(kernel),
            ctypes.byref(user),
        ):
            return None
        return (creation.high << 32) | creation.low
    finally:
        ctypes.windll.kernel32.CloseHandle(process)


class BotController:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.data_dir = self.root / "data"
        self.pid_path = self.data_dir / "browser_bot.pid"
        self.log_path = self.data_dir / "browser_bot.log"
        self.console_path = self.data_dir / "browser_bot_console.log"
        self._process: subprocess.Popen | None = None
        self._headless: bool | None = None
        self._console = None
        self._lock = threading.RLock()

    def _stored_identity(self) -> tuple[int, int, bool] | None:
        try:
            pid_text, created_text, mode = self.pid_path.read_text(encoding="ascii").split()
            if mode not in {"headless", "visible"}:
                return None
            return int(pid_text), int(created_text), mode == "headless"
        except (OSError, ValueError):
            return None

    def running_pid(self) -> int | None:
        with self._lock:
            if self._process is not None and self._process.poll() is None:
                return self._process.pid
            identity = self._stored_identity()
            if identity is not None:
                pid, created, headless = identity
                if process_is_running(pid) and process_creation_time(pid) == created:
                    self._headless = headless
                    return pid
            self.pid_path.unlink(missing_ok=True)
            self._headless = None
            return None

    def status_label(self) -> str:
        pid = self.running_pid()
        if pid is None:
            return "Bot arrêté"
        mode = "arrière-plan" if self._headless else "fenêtre visible"
        return f"Bot actif — {mode} (PID {pid})"

    def is_headless(self) -> bool | None:
        return self._headless if self.running_pid() is not None else None

    def start(self, *, headless: bool = True) -> int:
        with self._lock:
            pid = self.running_pid()
            if pid is not None:
                if self._headless == headless:
                    return pid
                self.stop()
            self.data_dir.mkdir(parents=True, exist_ok=True)
            self._console = self.console_path.open("a", encoding="utf-8")
            self._process = subprocess.Popen(
                build_bot_command(self.root, headless=headless),
                cwd=self.root,
                stdin=subprocess.DEVNULL,
                stdout=self._console,
                stderr=subprocess.STDOUT,
                creationflags=CREATE_NO_WINDOW,
            )
            created = process_creation_time(self._process.pid)
            if created is None:
                self._process.terminate()
                raise RuntimeError("Impossible d'identifier de façon sûre le processus du bot")
            self._headless = headless
            temporary = self.pid_path.with_suffix(".pid.tmp")
            mode = "headless" if headless else "visible"
            temporary.write_text(f"{self._process.pid} {created} {mode}", encoding="ascii")
            os.replace(temporary, self.pid_path)
            return self._process.pid

    def stop(self) -> bool:
        with self._lock:
            pid = self.running_pid()
            if pid is None:
                return False
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=CREATE_NO_WINDOW,
                check=False,
            )
            deadline = time.monotonic() + 5.0
            while process_is_running(pid) and time.monotonic() < deadline:
                time.sleep(0.1)
            self.pid_path.unlink(missing_ok=True)
            self._process = None
            self._headless = None
            if self._console is not None:
                self._console.close()
                self._console = None
            return True


def _single_instance() -> bool:
    handle = ctypes.windll.kernel32.CreateMutexW(None, False, MUTEX_NAME)
    if not handle:
        return False
    # Conserver la reference jusqu'a la fin du processus.
    _single_instance.handle = handle
    return ctypes.windll.kernel32.GetLastError() != ERROR_ALREADY_EXISTS


def run_tray(root: Path, *, initial_headless: bool = True) -> int:
    if not _single_instance():
        ctypes.windll.user32.MessageBoxW(None, "Cemanty Bot est déjà ouvert.", "Cemanty Bot", 0x40)
        return 0

    try:
        import pystray
    except ImportError:
        ctypes.windll.user32.MessageBoxW(
            None,
            "Le module pystray est absent. Lancez : pip install -r requirements.txt",
            "Cemanty Bot",
            0x10,
        )
        return 1

    icon_path = create_icon(root / "browser_bot" / "assets" / "cemanty_bot.ico")
    controller = BotController(root)

    def refresh(icon):
        icon.title = controller.status_label()
        icon.update_menu()

    def start(icon, _item):
        controller.start(headless=True)
        refresh(icon)

    def stop(icon, _item):
        controller.stop()
        refresh(icon)

    def show_site(icon, _item):
        controller.start(headless=False)
        refresh(icon)

    def hide_site(icon, _item):
        controller.start(headless=True)
        refresh(icon)

    def open_log(_icon, _item):
        controller.log_path.touch(exist_ok=True)
        os.startfile(controller.log_path)

    def quit_tray(icon, _item):
        controller.stop()
        icon.stop()

    menu = pystray.Menu(
        pystray.MenuItem(lambda _item: controller.status_label(), None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Démarrer le bot", start, enabled=lambda _item: controller.running_pid() is None),
        pystray.MenuItem("Arrêter le bot", stop, enabled=lambda _item: controller.running_pid() is not None),
        pystray.MenuItem(
            "Afficher Cemanty (profil connecté)",
            show_site,
            enabled=lambda _item: controller.is_headless() is not False,
        ),
        pystray.MenuItem(
            "Masquer Cemanty (mode autonome)",
            hide_site,
            enabled=lambda _item: controller.is_headless() is False,
        ),
        pystray.MenuItem("Ouvrir le journal", open_log),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quitter (arrête le bot)", quit_tray),
    )
    icon = pystray.Icon("cemanty_bot", Image.open(icon_path), controller.status_label(), menu)
    controller.start(headless=initial_headless)

    def monitor():
        previous = None
        while icon.visible:
            current = controller.running_pid()
            if current != previous:
                refresh(icon)
                previous = current
            time.sleep(2.0)

    def setup(active_icon):
        active_icon.visible = True
        threading.Thread(target=monitor, daemon=True).start()

    icon.run(setup=setup)
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="browser_bot.tray")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--visible", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    return run_tray(args.root, initial_headless=not args.visible)


if __name__ == "__main__":
    raise SystemExit(main())
