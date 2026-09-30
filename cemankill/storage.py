"""Enregistrement de tous les scores observes, par numero de jour (data/obs.json)."""
import json
import os


class ObsStore:
    def __init__(self, path: str):
        self.path = path

    def load(self) -> dict:
        try:
            with open(self.path, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}

    def save(self, day, observations) -> None:
        """observations : liste de (mot, score). Ecrit atomiquement pour ne jamais laisser un fichier tronque."""
        data = self.load()
        data[str(day)] = [[w, s] for w, s in observations]
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp, self.path)
