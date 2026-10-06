from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path

import chromadb
import fitz
from sentence_transformers import SentenceTransformer

from app.config import settings


SECTION_RE = re.compile(r"^SECTION\s+[A-Z](?:\.|\s)", re.IGNORECASE)
CLAUSE_RE = re.compile(
    r"^(?:Def\.\s*\d+\.|\d+(?:\.\d+){0,3}\.?\s+|[a-z]\.[\s]+|[ivxlcdm]+\.[\s]+)",
    re.IGNORECASE,
)


def clean_text(text: str) -> str:
    text = text.replace("\u00ad", "").replace("\u200b", "")
    text = re.sub(r"(?<=\w)-\s*\n\s*(?=\w)", "", text)
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def looks_like_heading(line: str) -> bool:
    if SECTION_RE.match(line) or CLAUSE_RE.match(line):
        return True
    letters = [c for c in line if c.isalpha()]
    if not letters:
        return False
    uppercase_ratio = sum(c.isupper() for c in letters) / len(letters)
    return len(line) <= 140 and uppercase_ratio > 0.85


def split_page_into_segments(
    text: str,
    inherited_section: str,
    inherited_clause: str = "Not explicitly identified",
) -> tuple[list[dict], str, str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    section = inherited_section or "Not explicitly identified"
    clause = inherited_clause or "Not explicitly identified"
    segments: list[dict] = []
    buffer: list[str] = []

    def flush() -> None:
        nonlocal buffer
        if buffer:
            segments.append(
                {"section": section, "clause": clause, "text": "\n".join(buffer).strip()}
            )
            buffer = []

    for line in lines:
        if SECTION_RE.match(line):
            flush()
            section = line
            clause = "Not explicitly identified"
            buffer = [line]
        elif looks_like_heading(line):
            flush()
            clause = line
            buffer = [line]
        else:
            buffer.append(line)
    flush()
    return segments, section, clause


def chunk_segment(text: str, size: int, overlap: int) -> list[str]:
    if len(text) <= size:
        return [text]
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + size)
        newline_boundary = text.rfind("\n", start, end)
        sentence_boundary = text.rfind(". ", start, end)
        boundary = max(newline_boundary, sentence_boundary)
        if boundary > start + size // 2:
            end = boundary + 1
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return chunks


def load_chunks(pdf_path: Path) -> list[dict]:
    document = fitz.open(pdf_path)
    chunks: list[dict] = []
    current_section = "Not explicitly identified"
    current_clause = "Not explicitly identified"

    for page_index, page in enumerate(document):
        text = clean_text(page.get_text("text"))
        if not text:
            continue
        segments, current_section, current_clause = split_page_into_segments(
            text, current_section, current_clause
        )
        for segment in segments:
            for part in chunk_segment(
                segment["text"], settings.chunk_size, settings.chunk_overlap
            ):
                chunks.append(
                    {
                        "text": part,
                        "page": page_index + 1,
                        "section": segment["section"],
                        "clause": segment["clause"],
                        "source": pdf_path.name,
                    }
                )
    document.close()
    return chunks


def index_policy(pdf_path: Path, rebuild: bool = False) -> int:
    if not pdf_path.exists():
        raise FileNotFoundError(
            f"Policy PDF not found at:\n{pdf_path}\n\nRun:\npython scripts/download_policy.py"
        )

    print("Reading policy PDF...")
    chunks = load_chunks(pdf_path)
    if not chunks:
        raise RuntimeError("No text could be extracted from the policy PDF.")
    print(f"Extracted {len(chunks)} chunks.")

    settings.chroma_dir.mkdir(parents=True, exist_ok=True)
    chroma = chromadb.PersistentClient(path=str(settings.chroma_dir))
    if rebuild:
        try:
            chroma.delete_collection(settings.chroma_collection)
        except Exception:
            pass

    collection = chroma.get_or_create_collection(
        name=settings.chroma_collection, metadata={"hnsw:space": "cosine"}
    )

    print(f"Loading local embedding model: {settings.embedding_model}")
    embedding_model = SentenceTransformer(settings.embedding_model)
    texts = [chunk["text"] for chunk in chunks]
    print("Generating embeddings locally...")
    embeddings = embedding_model.encode(
        texts,
        batch_size=32,
        show_progress_bar=True,
        normalize_embeddings=True,
    ).tolist()

    file_hash = hashlib.sha256(pdf_path.read_bytes()).hexdigest()[:16]
    ids = [f"{file_hash}-p{chunk['page']}-c{index}" for index, chunk in enumerate(chunks)]
    metadatas = [
        {
            "page": chunk["page"],
            "section": chunk["section"],
            "clause": chunk["clause"],
            "source": chunk["source"],
        }
        for chunk in chunks
    ]
    collection.upsert(ids=ids, documents=texts, metadatas=metadatas, embeddings=embeddings)
    return len(chunks)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create the local policy vector index.")
    parser.add_argument("--pdf", type=Path, default=settings.policy_path)
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    count = index_policy(args.pdf, rebuild=args.rebuild)
    print(f"\nSuccessfully indexed {count} policy chunks.")
    print(f"Collection: {settings.chroma_collection}")


if __name__ == "__main__":
    main()
