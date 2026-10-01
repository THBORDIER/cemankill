"""Persistance des mots refuses par la version web, par numero de jour."""
import json
import os


class RejectedStore:
    def __init__(self, path: str):
        self.path = path

    def _read(self) -> dict:
        try:
            with open(self.path, encoding="utf-8") as handle:
                return json.load(handle)
        except (OSError, ValueError):
            return {}

    def load(self, day) -> set:
        return set(self._read().get(str(day), []))

    def add(self, day, word: str) -> None:
        data = self._read()
        words = set(data.get(str(day), []))
        words.add(word)
        data[str(day)] = sorted(words)
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        temporary = self.path + ".tmp"
        with open(temporary, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False)
        os.replace(temporary, self.path)
