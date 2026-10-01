"""Etat du jeu web extrait du texte d'accessibilite de Cemanty."""
import re
from dataclasses import dataclass
from typing import Optional


_SCORE = r"[\-−]?\d+(?:[,.]\d+)?"


@dataclass(frozen=True)
class WebState:
    day: Optional[str] = None
    attempt: Optional[int] = None
    last_word: Optional[str] = None
    last_score: Optional[float] = None
    won: bool = False


def parse_number(value: str) -> float:
    return float(value.replace("−", "-").replace(",", "."))


def parse_snapshot(text: str) -> WebState:
    """Analyse le texte plat expose par la couche semantique du jeu Flutter."""
    day_match = re.search(r"Mot\s+n[°o]\s*(\d+)", text, re.IGNORECASE)
    day = day_match.group(1) if day_match else ("bonus" if "Bonus du jour" in text else None)

    result = re.search(
        rf"DERNIER MOT\s*[·•]\s*ESSAI\s*(\d+)\s*\n\s*([^\n]+?)\s*\n\s*({_SCORE})(?:\s*\n|$)",
        text,
        re.IGNORECASE,
    )
    if result:
        score = parse_number(result.group(3))
        return WebState(day, int(result.group(1)), result.group(2).strip(), score, score >= 99.995)

    bonus_result = re.search(
        rf"(?:^|\n)\s*([^\n]+?)\s*\n\s*essai\s+(\d+)\s*\n\s*({_SCORE})(?:\s*\n|$)",
        text,
        re.IGNORECASE,
    )
    if day == "bonus" and bonus_result:
        score = parse_number(bonus_result.group(3))
        return WebState(
            day,
            int(bonus_result.group(2)),
            bonus_result.group(1).strip(),
            score,
            score >= 99.995,
        )

    victory = re.search(
        r"Tu as trouv[ée]\s*[«\"]?\s*([^»\"\n]+?)\s*[»\"]?\s*(?:en\s+(\d+)\s+essais?)?(?:\s*!|$)",
        text,
        re.IGNORECASE,
    )
    if victory:
        attempt = int(victory.group(2)) if victory.group(2) else None
        return WebState(day, attempt, victory.group(1).strip(), 100.0, True)

    return WebState(day=day)
