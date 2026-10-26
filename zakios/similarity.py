"""Présélection par TF-IDF et cosinus. Un score n'est qu'un indice, pas une preuve."""
import math
import re
from collections import Counter, defaultdict

_STOP = frozenset("""a an the and or of to in for with on is are be as by at from that this it its you your use when
will can not do does into any all more most also such than then they their them has have had was were been
should would could may might must about over under between per via etc using used uses""".split())
_TOKEN = re.compile(r"[a-z][a-z0-9\-]{2,}")


def tokens(text):
    return [w for w in _TOKEN.findall(text.lower()) if w not in _STOP]


def vectorize(texts):
    """Vecteurs TF-IDF normalisés, dans l'ordre des textes (résultat déterministe)."""
    docs = [Counter(tokens(t)) for t in texts]
    n = len(docs)
    df = Counter()
    for doc in docs:
        df.update(doc.keys())
    vectors = []
    for doc in docs:
        vec = {w: (1 + math.log(c)) * math.log(n / df[w]) for w, c in doc.items()}
        norm = math.sqrt(sum(x * x for x in vec.values())) or 1.0
        vectors.append({w: x / norm for w, x in vec.items()})
    return vectors


class Index:
    """Index inversé sur un sous-ensemble de composants."""

    def __init__(self, vectors, ids, members):
        self._ids = ids
        self._post = defaultdict(list)
        for i in members:
            for word, weight in vectors[i].items():
                self._post[word].append((i, weight))

    def top(self, vec, k=1, exclude=None):
        """Les k meilleurs voisins sous la forme (indice, score), départagés par identifiant."""
        scores = defaultdict(float)
        for word, weight in vec.items():
            for i, other in self._post.get(word, ()):
                scores[i] += weight * other
        ranked = sorted(((-s, self._ids[i], i) for i, s in scores.items() if i != exclude))
        return [(i, round(-neg, 4)) for neg, _, i in ranked[:k]]
