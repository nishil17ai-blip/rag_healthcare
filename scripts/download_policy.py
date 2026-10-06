from __future__ import annotations

import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import settings  # noqa: E402


def main() -> None:
    target = settings.policy_path
    target.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading policy from:\n{settings.policy_url}")
    response = requests.get(
        settings.policy_url,
        timeout=60,
        headers={"User-Agent": "Mozilla/5.0 Policy-RAG-Assignment/1.0"},
    )
    response.raise_for_status()
    content_type = response.headers.get("content-type", "").lower()
    if "pdf" not in content_type and not response.content.startswith(b"%PDF"):
        raise RuntimeError(
            f"Expected a PDF but received content-type '{content_type}'. "
            "Download the policy manually from the assignment URL and place it at "
            f"{target}."
        )
    target.write_bytes(response.content)
    print(f"Saved: {target} ({len(response.content):,} bytes)")


if __name__ == "__main__":
    main()
