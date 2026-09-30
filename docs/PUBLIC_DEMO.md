# SIH public evaluation demo

The hosted instance provides convenient SIH evaluation of PS 26146. The same
platform remains capable of local/offline deployment; see [README_OFFLINE](../README_OFFLINE.md).
A public HTTPS container host runs FastAPI. GitHub Pages cannot run this backend.

```text
Judge browser -> Public HTTPS host -> Docker container
                                      |-- FastAPI + local dashboard
                                      |-- Frozen tuned-42 ML model
                                      |-- Graph engine
                                      +-- Synthetic demonstration dataset
```

## Build and run (repository root)

Docker Desktop must use Linux containers. The frozen artifact requires exact
CPython 3.13.14 and the existing scientific dependency lock. The Dockerfile pins
the verified Python image digest. It builds frontend assets once during image
creation, verifies model checksums and compatibility, and never fits a model.

```powershell
.\venv\Scripts\python.exe -B scripts/stage_demo_model.py
docker build -t bitcoin-transaction-intelligence:sih-demo .
docker run --name sih-demo --read-only --cap-drop ALL --security-opt no-new-privileges -e PUBLIC_DEMO=true -p 127.0.0.1:8000:8000 bitcoin-transaction-intelligence:sih-demo
# In another terminal:
.\venv\Scripts\python.exe -B scripts/smoke_container.py
docker inspect --format '{{.State.Health.Status}}' sih-demo
docker stop sih-demo
docker rm sih-demo
```

Open http://127.0.0.1:8000. The process binds `0.0.0.0` inside the container.
`PORT` defaults to 8000; when overridden, map the same internal port. Public mode
preloads inference/graph before accepting requests. `/api/health` plus its
`graph_status=ready` is the readiness check. Docker probes it using Python.

## Frozen model handoff

The model remains Git-ignored. `scripts/stage_demo_model.py` verifies the three
existing files in `artifacts/ml/tuning/run-001/tuned-42/` against reviewed hashes
in `deploy/model_checksums.json`, then copies them to ignored `.container-model/`.
Missing or modified files fail staging and image verification. A Git clone alone
is insufficient. Do not retrain to supply missing files.

**One manual prerequisite for Actions:** upload those exact three trusted files
as assets of a GitHub release tagged `frozen-demo-model` in this repository.
This makes the demonstration model distributable, as it will also be in the image.
From the trusted workspace, after reviewing and pushing the deployment branch:

```powershell
.\venv\Scripts\python.exe -B scripts/stage_demo_model.py
gh release create frozen-demo-model .container-model/pipeline.joblib .container-model/manifest.json .container-model/threshold.json --target feat/containerized-public-demo --title "Frozen SIH demo model" --notes "Existing tuned-42 artifact; checksums in deploy/model_checksums.json. No retraining."
```

The manual `publish-demo.yml` workflow downloads only these assets using
`GITHUB_TOKEN`, verifies fixed checksums, builds Linux/amd64, smoke-tests startup,
read-only mode and restart, then publishes `latest`, `sih-2026` and `sha-<commit>`.
Owner/repository names come from GitHub context and are lowercased. Permissions
are `contents: read` and `packages: write`; no personal token is needed.
No workflow runs on ordinary documentation commits. Actions publishing has not
been exercised until a real dispatch succeeds. Workflow dispatch availability
requires the workflow on the repository's default branch; merge the reviewed PR
before dispatching through the standard GitHub UI/CLI.

```powershell
gh workflow run publish-demo.yml --ref main
gh run list --workflow publish-demo.yml
# Once the workflow succeeds (replace placeholders):
docker pull ghcr.io/<github-owner>/<repository-name>:sih-2026
docker run --rm --read-only --cap-drop ALL --security-opt no-new-privileges -e PUBLIC_DEMO=true -p 127.0.0.1:8000:8000 ghcr.io/<github-owner>/<repository-name>:sih-2026
```

After publication, change package visibility to Public under the package's
Settings if anonymous pulls are required. Verify a pull without credentials.
Version tags can be moved; deploy the published `@sha256:<digest>` for immutable
identity. See [GitHub publishing guidance](https://docs.github.com/en/actions/tutorials/publish-packages/publish-docker-images)
and [GHCR visibility guidance](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry).

## Public safety and demo

`PUBLIC_DEMO=true` rejects all HTTP mutation methods with 403 before request-body
parsing, including `/ingest`. GET investigation endpoints and local assets remain
available. Local/offline mode defaults to unchanged ingestion behavior when this
variable is unset. Keep public mode enabled on public hosts. No training,
configuration editing, deletion, shell execution or file-writing API is exposed.
The process runs as UID/GID 10001, supports a read-only filesystem, and writes
logs to stdout/stderr. No persistent database, volume, external API, CDN, browser
launch or internet connection is required after image creation. Existing bounded
queries remain unchanged; use host-level request/rate limits for public traffic.

The existing initial alert selection already loads the known example, so no
redundant demo button was added. Search these exact identifiers:

- Transaction: `6438536fd7ddeb015a2a0a7e5cc5f0d2df04d600d9ea0592c9fa3f1a41db3202`
- Address: `1ESbdF6ACUgGWDe9fvPjeisQRNLWvzPJtE`
- Expected counts: 18,000 transactions; 7,059 addresses; 60,836 directed
  relationships; 6,153 frozen-threshold flags.
- The [30-transaction/58-second walkthrough](demo_walkthrough.md) is
  evaluation-selected, not a model discovery.

All data are synthetic Bitcoin-like observations. Scores are investigative
indicators, not probabilities of crime. Address/network relationships do not
prove ownership, identity, illicit activity or specific UTXO spends.

## Host requirements and troubleshooting

Use a Linux/amd64 container host with HTTPS termination, configurable `PORT`,
a startup grace period of at least 180 seconds, `/api/health` readiness, and no
persistent database requirement. Start planning with 1 CPU and 2 GiB RAM for one
worker; this is provisioning headroom, not a proven concurrency capacity. See
`reports/deployment/verification.json` for actual image size/startup/memory when
available. Allow image storage plus registry download/extraction headroom.
Cold starts repeat ingestion, inference and graph construction, never training.
Use the image's default command (`python -B deploy/start.py`). Do not override it
with a localhost-only bind. Select a provider only after reviewing measured needs.

- Missing staging: obtain the trusted files and run the staging command.
- Dependency/image download failure: builds need registry/package network access;
  runtime does not. Never loosen the frozen compatibility guard to bypass it.
- Startup failure: inspect `docker logs sih-demo`; verify pinned versions and
  artifact checksums. Detailed logs are operator-only; HTTP errors are generic.
- Port conflict: stop the existing owned instance or map another host port.
- 403 on ingestion: expected in public mode. Use private/local mode for ingestion.
- Unhealthy while starting: allow preload time; inspect memory limits and logs.
- This deployment does not certify a clean-machine offline Linux installation,
  an actual public HTTPS URL, external-device access or GHCR publication.
