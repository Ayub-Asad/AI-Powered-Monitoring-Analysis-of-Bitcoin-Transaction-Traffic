"""FastAPI entry point.  Run:  uvicorn app.main:app --reload"""
import logging
import os
from typing import Optional

from fastapi import FastAPI, File, Query, UploadFile
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from .ingestion import supported_formats
from .service import process_upload

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

app = FastAPI(
    title="Bitcoin Transaction Analysis API",
    version="0.1.0",
    description="PS 26146 - ingestion layer (validation, normalisation, canonical schema).",
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "btc-analysis-api", "supported_formats": supported_formats()}


@app.post("/ingest")
async def ingest(
    file: UploadFile = File(..., description="CSV, JSON or JSONL transaction file"),
    fmt: Optional[str] = Query(None, alias="format", description="Override format detection (csv|json|jsonl)"),
) -> JSONResponse:
    data = await file.read()
    status_code, body = await run_in_threadpool(process_upload, file.filename or "upload", data, fmt)
    return JSONResponse(status_code=status_code, content=body)
