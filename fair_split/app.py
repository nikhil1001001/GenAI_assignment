from __future__ import annotations

import logging
import os
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from fair_split.pipeline.orchestrator import split_bill
from fair_split.serialization import result_to_contract

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

app = FastAPI(title="Fair Split API", version="1.0.0")


class SplitRequest(BaseModel):
    receipt_base64: str
    description: str


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/split")
def split(request: SplitRequest) -> dict:
    result = split_bill(request.receipt_base64, request.description)
    return result_to_contract(result)


if FRONTEND.exists():
    app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="frontend")


def run(host: str = "127.0.0.1", port: int | None = None) -> None:
    uvicorn.run(
        "fair_split.app:app",
        host=host,
        port=port or int(os.getenv("PORT", "8000")),
    )


if __name__ == "__main__":
    run()
