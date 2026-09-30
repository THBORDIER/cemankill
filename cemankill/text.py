"""Outils sur les mots : retrait des accents (adb input text est limite a l'ASCII) et formes voisines."""
import unicodedata


def strip_accents(word: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", word) if unicodedata.category(c) != "Mn")


def variants(word: str) -> set:
    """Formes que le jeu score comme le mot lui-meme (pluriel, feminin...) : inutile de les essayer."""
    out = {word + "s", word + "x", word + "es", word + "e", word.rstrip("sx")}
    if word.endswith("es"):
        out.add(word[:-2])
    if word.endswith("al"):
        out.add(word[:-2] + "aux")
    out.discard(word)
    return out
