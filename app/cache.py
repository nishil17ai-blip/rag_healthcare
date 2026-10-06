from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from sentence_transformers import SentenceTransformer

from app.config import settings


@dataclass
class CacheEntry:
    question: str
    embedding: np.ndarray
    response: Any


class SemanticCache:

    def __init__(
        self,
        threshold: float = 0.92,
        max_entries: int = 200,
    ) -> None:

        self.threshold = threshold
        self.max_entries = max_entries

        self.model = SentenceTransformer(
            settings.embedding_model
        )

        self.entries: list[CacheEntry] = []

    def _embed(
        self,
        text: str
    ) -> np.ndarray:

        return self.model.encode(
            text,
            normalize_embeddings=True,
        )

    def get(
        self,
        question: str
    ):

        if not self.entries:
            return None

        query_embedding = self._embed(
            question
        )

        best_score = -1.0
        best_entry = None

        for entry in self.entries:

            score = float(
                np.dot(
                    query_embedding,
                    entry.embedding,
                )
            )

            if score > best_score:
                best_score = score
                best_entry = entry

        if (
            best_entry is not None
            and best_score >= self.threshold
        ):
            return best_entry.response

        return None

    def put(
        self,
        question: str,
        response,
    ) -> None:

        embedding = self._embed(
            question
        )

        self.entries.append(
            CacheEntry(
                question=question,
                embedding=embedding,
                response=response,
            )
        )

        if len(self.entries) > self.max_entries:
            self.entries.pop(0)