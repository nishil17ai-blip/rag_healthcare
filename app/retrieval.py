from __future__ import annotations

import chromadb
from sentence_transformers import SentenceTransformer

from app.config import settings


class PolicyRetriever:
    def __init__(self) -> None:
        print("Loading embedding model for retrieval...")
        self.embedding_model = SentenceTransformer(settings.embedding_model)
        self.chroma = chromadb.PersistentClient(path=str(settings.chroma_dir))
        try:
            self.collection = self.chroma.get_collection(settings.chroma_collection)
        except Exception as exc:
            raise RuntimeError(
                "Policy vector database was not found.\nRun:\npython -m app.ingest --rebuild"
            ) from exc

    def search(self, question: str, top_k: int | None = None) -> list[dict]:
        k = top_k or settings.top_k
        question_embedding = self.embedding_model.encode(
            question, normalize_embeddings=True
        ).tolist()
        result = self.collection.query(
            query_embeddings=[question_embedding],
            n_results=k,
            include=["documents", "metadatas", "distances"],
        )

        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]
        items: list[dict] = []

        for index, (document, metadata, distance) in enumerate(
            zip(documents, metadatas, distances), start=1
        ):
            items.append(
                {
                    "id": f"S{index}",
                    "text": document,
                    "page": int(metadata.get("page", 0)),
                    "section": metadata.get("section") or "Not explicitly identified",
                    "clause": metadata.get("clause") or "Not explicitly identified",
                    "source": metadata.get("source") or "Policy document",
                    "distance": float(distance),
                }
            )
        return items


def context_block(items: list[dict]) -> str:
    return "\n\n---\n\n".join(
        (
            f"[{item['id']}]\n"
            f"Page: {item['page']}\n"
            f"Section: {item['section']}\n"
            f"Clause: {item['clause']}\n"
            f"Text:\n{item['text']}"
        )
        for item in items
    )
