"""Lecture de l'ecran a partir de l'arbre d'accessibilite (uiautomator dump). Aucune dependance a adb : testable avec du XML."""
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Optional, Tuple

from . import config

_BOUNDS = re.compile(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]")
_NOISE = ("/1000", "1000")      # fragments repetes dans chaque ligne de resultat, sans interet


@dataclass(frozen=True)
class Node:
    text: str
    cls: str
    bounds: Tuple[int, int, int, int]

    @property
    def center(self) -> Tuple[int, int]:
        b = self.bounds
        return (b[0] + b[2]) // 2, (b[1] + b[3]) // 2


class Screen:
    def __init__(self, nodes):
        self.nodes = list(nodes)
        self.texts = [n.text for n in self.nodes if n.text and n.text not in _NOISE]

    @classmethod
    def from_xml(cls, xml: str) -> "Screen":
        nodes = []
        try:
            root = ET.fromstring(xml)
        except ET.ParseError:
            return cls([])
        for n in root.iter("node"):
            text = n.get("text") or n.get("content-desc") or ""
            m = _BOUNDS.match(n.get("bounds") or "")
            bounds = tuple(map(int, m.groups())) if m else (0, 0, 0, 0)
            nodes.append(Node(text, n.get("class") or "", bounds))
        return cls(nodes)

    def has(self, s: str) -> bool:
        return any(s in t for t in self.texts)

    def has_any(self, markers) -> bool:
        return any(self.has(m) for m in markers)

    def find(self, s: str, last: bool = False) -> Optional[Node]:
        found = [n for n in self.nodes if s in n.text]
        if not found:
            return None
        return found[-1] if last else found[0]

    def edit_text(self) -> Optional[Node]:
        return next((n for n in self.nodes if n.cls == "android.widget.EditText"), None)


@dataclass(frozen=True)
class GameState:
    in_game: bool
    field: str                  # contenu du champ de saisie ('' ou texte indicatif si vide)
    day: Optional[str]          # numero du mot (ex. '61')
    last_word: Optional[str]    # dernier mot essaye, tel qu'affiche par le jeu
    last_score: Optional[float]
    ad: bool
    achievement: bool
    finished: bool

    @property
    def field_dirty(self) -> bool:
        """Vrai si le champ contient un mot (donc le mot envoye a ete refuse)."""
        return bool(self.field) and not self.field.startswith(config.HINT_PREFIX)


def parse_score(text: str) -> Optional[float]:
    """'26,27' -> 26.27 ; '−2,16' (signe moins typographique) -> -2.16."""
    try:
        return float(text.replace(",", ".").replace("−", "-"))
    except (ValueError, AttributeError):
        return None


def parse_state(screen: Screen) -> GameState:
    edit = screen.edit_text()
    header_i = next((k for k, t in enumerate(screen.texts) if t.startswith("Mot n")), None)
    archive_game = screen.has("Archive") and header_i is not None and edit is not None
    in_game = "Abandonner" in screen.texts or archive_game
    ad = screen.has_any(config.AD_MARKERS)
    achievement = screen.has_any(config.ACHIEVEMENT_MARKERS)
    day = last_word = last_score = None
    if in_game and header_i is not None:
        if header_i + 3 < len(screen.texts):
            m = re.search(r"n° (\d+)", screen.texts[header_i])
            day = m.group(1) if m else None
            last_word = screen.texts[header_i + 1]
            last_score = parse_score(screen.texts[header_i + 3])
    finished = (screen.has("Terminer") or any(t.startswith("Tu as trouv") for t in screen.texts)
                or (not in_game and not ad and not achievement))
    return GameState(in_game, edit.text if edit else "", day, last_word, last_score, ad, achievement, finished)
