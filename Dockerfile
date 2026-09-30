# Exact CPython patch and scientific dependencies preserve artifact compatibility.
FROM python:3.13.14-slim-bookworm@sha256:67a1e1f215ccda113cfc024e8639049257e88f273898f595b61476d128d387e8
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8000 PUBLIC_DEMO=true OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
WORKDIR /app
COPY backend/requirements-offline-lock.txt backend/requirements-offline-lock.txt
RUN python -m pip install --no-cache-dir --only-binary=:all: -r backend/requirements-offline-lock.txt \
    && python -m pip check
COPY backend/app/ backend/app/
COPY frontend/src/ frontend/src/
COPY data/v2/development.csv data/v2/development.csv
COPY scripts/build_dashboard.py scripts/stage_demo_model.py scripts/
COPY deploy/ deploy/
# Run scripts/stage_demo_model.py before building; absent staging fails COPY.
COPY .container-model/ artifacts/ml/tuning/run-001/tuned-42/
RUN python scripts/stage_demo_model.py --verify-only \
    && python scripts/build_dashboard.py \
    && python -c "import sys; sys.path.insert(0, 'backend'); from app.ml.artifacts import load_artifact; load_artifact('artifacts/ml/tuning/run-001/tuned-42')"
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=180s --retries=3 \
    CMD ["python", "-B", "deploy/healthcheck.py"]
CMD ["python", "-B", "deploy/start.py"]
