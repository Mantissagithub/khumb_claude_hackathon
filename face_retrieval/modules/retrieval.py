"""Vector database for face retrieval — FAISS with a numpy fallback.

Embeddings are L2-normalised upstream, so cosine similarity == inner product
(FAISS IndexFlatIP). `search` always returns similarity where HIGHER = closer,
for both cosine and l2 (l2 distance is returned negated), so downstream code
can treat results uniformly.
"""
from __future__ import annotations

import os
import pickle
from typing import Optional

import numpy as np


def _faiss_available() -> bool:
    import importlib.util
    return importlib.util.find_spec("faiss") is not None


class VectorIndex:
    def __init__(self, dim: int, backend: str = "auto", metric: str = "cosine",
                 logger=None):
        self.dim = dim
        self.metric = metric
        self.log = logger
        self.ids: list = []
        self.backend = self._select(backend)
        self._index = None          # faiss index
        self._mat: Optional[np.ndarray] = None  # numpy fallback store
        if self.backend == "faiss":
            import faiss
            self._faiss = faiss
            self._index = (faiss.IndexFlatIP(dim) if metric == "cosine"
                           else faiss.IndexFlatL2(dim))
        if logger:
            logger.info("vector_db backend = %s (metric=%s)", self.backend, metric)

    def _select(self, want: str) -> str:
        want = (want or "auto").lower()
        if want == "faiss" or (want == "auto" and _faiss_available()):
            return "faiss"
        return "numpy"

    # -- build / add --------------------------------------------------------
    def build_index(self, embeddings: np.ndarray, ids: list) -> None:
        embeddings = np.ascontiguousarray(embeddings.astype("float32"))
        assert embeddings.shape[1] == self.dim, "embedding dim mismatch"
        self.ids = list(ids)
        if self.backend == "faiss":
            self._index.reset()
            self._index.add(embeddings)
        else:
            self._mat = embeddings.copy()

    def add(self, embeddings: np.ndarray, ids: list) -> None:
        embeddings = np.ascontiguousarray(embeddings.astype("float32"))
        self.ids.extend(ids)
        if self.backend == "faiss":
            self._index.add(embeddings)
        else:
            self._mat = embeddings if self._mat is None else np.vstack([self._mat, embeddings])

    @property
    def size(self) -> int:
        return len(self.ids)

    # -- search -------------------------------------------------------------
    def search(self, query: np.ndarray, top_k: int = 10):
        """Return (scores [Q,k], indices [Q,k]). Higher score = more similar."""
        q = np.atleast_2d(query.astype("float32"))
        k = min(top_k, max(self.size, 1))
        if self.backend == "faiss":
            sims, idx = self._index.search(np.ascontiguousarray(q), k)
            if self.metric == "l2":
                sims = -sims  # distance -> similarity
            return sims, idx
        # numpy fallback
        if self.metric == "cosine":
            sims = q @ self._mat.T
        else:
            sims = -((q[:, None, :] - self._mat[None, :, :]) ** 2).sum(-1)
        idx = np.argsort(-sims, axis=1)[:, :k]
        top = np.take_along_axis(sims, idx, axis=1)
        return top, idx

    def search_ids(self, query: np.ndarray, top_k: int = 10) -> list[list[tuple]]:
        """Convenience: list (per query) of (id, score) sorted best-first."""
        sims, idx = self.search(query, top_k)
        out = []
        for row_s, row_i in zip(sims, idx):
            out.append([(self.ids[i], float(s)) for s, i in zip(row_s, row_i) if i >= 0])
        return out

    # -- persistence --------------------------------------------------------
    def save_index(self, path: str) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        meta = {"dim": self.dim, "metric": self.metric, "backend": self.backend,
                "ids": self.ids}
        if self.backend == "faiss":
            self._faiss.write_index(self._index, path + ".faiss")
        else:
            np.save(path + ".npy", self._mat)
        with open(path + ".meta.pkl", "wb") as f:
            pickle.dump(meta, f)

    @classmethod
    def load_index(cls, path: str, logger=None) -> "VectorIndex":
        with open(path + ".meta.pkl", "rb") as f:
            meta = pickle.load(f)
        obj = cls(meta["dim"], backend=meta["backend"], metric=meta["metric"], logger=logger)
        if meta["backend"] == "faiss":
            obj._index = obj._faiss.read_index(path + ".faiss")
        else:
            obj._mat = np.load(path + ".npy")
        obj.ids = meta["ids"]
        return obj
