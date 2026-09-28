"""FastAPI entry point.  Run:  uvicorn app.main:app --reload"""
import logging
import os
from typing import Optional

from fastapi import FastAPI, File, Query, UploadFile
from fastapi.responses import JSONResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from .ingestion import supported_formats
from .service import process_upload
from .investigation import router, ROOT

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

app = FastAPI(
    title="Bitcoin Transaction Intelligence Platform",
    version="0.2.0",
    description="PS 26146 - offline ingestion and graph investigation.",
    docs_url=None,
    redoc_url=None,
)
app.include_router(router)
app.mount('/assets', StaticFiles(directory=ROOT / 'frontend/dist', check_dir=False), name='dashboard-assets')


@app.get('/docs', include_in_schema=False)
@app.get('/redoc', include_in_schema=False)
def offline_api_contract():
    """Avoid FastAPI's default CDN-backed documentation pages offline."""
    return RedirectResponse('/openapi.json')


@app.get('/', include_in_schema=False)
def dashboard():
    index = ROOT / 'frontend/dist/index.html'
    if not index.exists():
        return JSONResponse(status_code=503, content={'detail': 'Run python scripts/build_dashboard.py first'})
    return FileResponse(index)


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
