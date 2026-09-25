"""The scan behind the search by meaning (docs/decisions/027): the similarity of a message to
every passage. One matrix product when numpy is installed, a plain loop when it is not; both give
the same answer to within float rounding. Nothing to configure: numpy is used if it can be imported."""

from array import array
from typing import Sequence

from sympose.engine import embeddings

try:
    import numpy
except ImportError:  # optional: `pip install "sympose[fast]"`
    numpy = None


class VectorSet:
    """The unit vectors of a list of passages, and their similarity to a unit-length query."""

    def __init__(self, vectors: list[array]) -> None:
        self.dims = len(vectors[0]) if vectors else 0
        self._np = numpy  # the path this set was built for
        if self._np is not None and vectors:
            self._matrix = self._np.vstack([self._np.frombuffer(v, dtype=self._np.float32) for v in vectors])
            self._rows: list[array] = []
        else:
            self._matrix = None
            self._rows = vectors

    def scores(self, query: Sequence[float]) -> list[float]:
        """The cosine of `query` (unit length) with each vector, in the order they were given."""
        if self._matrix is not None:
            return (self._matrix @ self._np.asarray(query, dtype=self._np.float32)).tolist()
        return [embeddings.dot(query, row) for row in self._rows]
