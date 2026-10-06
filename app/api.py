from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.workflow import InsuranceAssistant


STATIC_DIR = Path(__file__).resolve().parent / "static"


app = FastAPI(
    title="Health Insurance Policy Assistant",
    version="2.0.0",
    description="Policy-grounded RAG assistant",
)


app.mount(
    "/static",
    StaticFiles(directory=STATIC_DIR),
    name="static",
)


@lru_cache(maxsize=1)
def get_assistant() -> InsuranceAssistant:
    return InsuranceAssistant()


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(
        STATIC_DIR / "index.html"
    )


@app.get("/health")
def health():
    return {
        "status": "ok"
    }


@app.get(
    "/policy-document",
    include_in_schema=False
)
def policy_document():

    if not settings.policy_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Policy document not found."
        )

    return FileResponse(
        path=settings.policy_path,
        media_type="application/pdf",
        filename="optima-secure-policy.pdf",
        content_disposition_type="inline",
    )


@app.post("/ask")
def ask(
    question: str = Form(...)
):
    try:

        assistant = get_assistant()

        return assistant.ask(
            question
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=str(exc)
        )