from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parents[1]


def _resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT_DIR / path


@dataclass(frozen=True)
class Settings:
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    model: str = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
    embedding_model: str = os.getenv(
        "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
    )

    policy_url: str = os.getenv(
        "POLICY_URL",
        "https://www.hdfcergo.com/docs/default-source/downloads/"
        "policy-wordings/health/optima-secure-revision-pw.pdf",
    )
    policy_path: Path = _resolve_path(
        os.getenv("POLICY_PATH", "data/policy/optima-secure-revision-pw.pdf")
    )
    chroma_dir: Path = _resolve_path(os.getenv("CHROMA_DIR", "data/chroma"))
    chroma_collection: str = os.getenv("CHROMA_COLLECTION", "policy_chunks")

    top_k: int = int(os.getenv("TOP_K", "8"))
    chunk_size: int = int(os.getenv("CHUNK_SIZE", "1800"))
    chunk_overlap: int = int(os.getenv("CHUNK_OVERLAP", "250"))


settings = Settings()


def require_groq_key() -> None:
    if not settings.groq_api_key or settings.groq_api_key.startswith("gsk_your"):
        raise RuntimeError(
            "GROQ_API_KEY is missing. Add your Groq API key to the .env file."
        )
