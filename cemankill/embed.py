"""Construit vocab.txt + emb.npy (embeddings bge-m3 via Ollama) depuis fr_50k.txt."""
import os, re, json, sys, urllib.request, numpy as np
OK = re.compile(r"^[a-zàâäçéèêëîïôöùûüÿœæ]+(-[a-zàâäçéèêëîïôöùûüÿœæ]+)?$")
DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
N = int(sys.argv[1]) if len(sys.argv) > 1 else 40000
words = []
for line in open(os.path.join(DATA, "fr_50k.txt"), encoding="utf-8"):
    w = line.split()[0].lower()
    if 3 <= len(w) <= 16 and OK.match(w) and w not in words[-1:]:
        words.append(w)
    if len(words) >= N: break
words = list(dict.fromkeys(words))
def embed(batch):
    req = urllib.request.Request("http://127.0.0.1:11434/api/embed",
        json.dumps({"model": "bge-m3", "input": batch}).encode(), {"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=300))["embeddings"]
out = []
for i in range(0, len(words), 200):
    out += embed(words[i:i+200])
    if (i // 200) % 10 == 0: print(i, len(words), flush=True)
E = np.array(out, dtype=np.float32)
E /= np.linalg.norm(E, axis=1, keepdims=True)
np.save(os.path.join(DATA, "emb.npy"), E)
open(os.path.join(DATA, "vocab.txt"), "w", encoding="utf-8").write("\n".join(words))
print("ok", E.shape)
