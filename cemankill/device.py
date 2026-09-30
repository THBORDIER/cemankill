"""Appareil Android pilote par adb. Seule couche qui parle au systeme : le reste du code ne connait que cette interface."""
import re
import subprocess

from . import config
from .screen import Screen


class AdbDevice:
    def __init__(self, adb: str = config.ADB):
        self.adb = adb

    def _run(self, *args, timeout: int = 30) -> str:
        r = subprocess.run([self.adb, *args], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout)
        return r.stdout

    def screen(self) -> Screen:
        """Texte de tout l'ecran (arbre d'accessibilite) : bien moins cher qu'une capture d'image."""
        self._run("shell", "uiautomator", "dump", "/sdcard/u.xml")
        return Screen.from_xml(self._run("shell", "cat", "/sdcard/u.xml"))

    def foreground(self) -> str:
        """Paquet de l'appli au premier plan ('' si inconnu) : detecte une pub qui a ouvert Chrome ou le Play Store."""
        m = re.search(r"mCurrentFocus=Window\{\S+ \S+ ([\w.]+)/", self._run("shell", "dumpsys", "window"))
        return m.group(1) if m else ""

    def launch(self, package: str, activity: str) -> None:
        self._run("shell", "am", "start", "-n", f"{package}/{activity}")

    def tap(self, x: int, y: int) -> None:
        self._run("shell", "input", "tap", str(x), str(y))

    def swipe(self, x1: int, y1: int, x2: int, y2: int, ms: int = 300) -> None:
        self._run("shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(ms))

    def type_text(self, text: str) -> None:
        """ASCII uniquement (limite de `input text`)."""
        self._run("shell", "input", "text", text)

    def key(self, name: str) -> None:
        self._run("shell", "input", "keyevent", name)
