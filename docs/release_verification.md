# Release verification - 2026-09-29

**WARNING: Linux packaging prepared; execution verification pending.**

Final regression: 265 tests + 75 subtests passed, zero failures/skips, one known
Starlette/httpx warning, 176.96s. Focused release suite: 10 passed, 6.95s.
The first regression run passed in 183.04s; the suite was rerun after correcting
the dashboard manifest's platform-dependent newline output. The initial focused
root-invoked import test failed once and was fixed before the passing reruns.

See compact evidence in [verification.json](../reports/release/verification.json),
[checks.json](../reports/release/checks.json), [HTTP smoke](../reports/release/http.json),
[browser smoke](../reports/release/browser.json), [relocated runtime](../reports/release/relocated_runtime.json)
and [restart smoke](../reports/release/restart.json). Timings are observations under
varying concurrent load, not performance benchmarks.

## Scope and audit

- Application source, ML/data freezes, graph semantics and frontend design are
  unchanged. All 248 protected-file hashes match the existing inventory.
- `scripts/build_dashboard.py` now writes the asset manifest as UTF-8/LF on both
  systems. `scripts/smoke_dashboard.py` accepts a separate URL and output report
  so release verification does not overwrite historical dashboard evidence.
- Default dataset/model/static paths resolve relative to source files, including
  from a relocated bundle with spaces in its path and an unrelated working directory.
  Runtime environment overrides retain their existing semantics; verification
  explicitly requires the default demo inputs. No Windows subprocess, executable,
  temporary directory or path separator is required by normal application startup.
- Frozen experiment-only `ml/final_evaluation.py` retains historical Windows
  fixture-inventory context. `ml/artifacts.py` invokes Git for training provenance
  only. Neither operation is on the inference/dashboard runtime path; their frozen
  history was preserved. No case mismatch was found in required runtime filenames.
- Runtime URL search found only the W3C SVG namespace, which performs no fetch.
  Frontend API fetches use local relative paths. API documentation redirects to
  local OpenAPI JSON. README/PROJECT_CONTEXT/docs URL matches were localhost command
  examples, separately from runtime code. No CDN, remote font/API/analytics/GeoIP
  runtime dependency was found.
- CPython 3.13.14 and exact scientific versions are required by the existing trusted
  artifact guard. Runtime pins derive from installed dependency metadata. Linux
  dependency closure/wheel availability must still be checked by actually running
  the wheelhouse builder on the matching target platform; no broad Python/OS
  compatibility claim is made.

## Executed packaging and runtime checks

- 65 runtime files hashed; preparation tar contains 66 allowlisted members including
  the release manifest. No corpora, other models, sidecars, caches, venv or secrets.
  The 5,894,413-byte preparation archive and SHA-256 are recorded in checks.json.
- Archive extraction, dashboard rebuild and checksum verification passed. The
  extracted minimal bundle loaded its own dataset/model and passed ASGI/API graph
  checks while Python networking was denied (45.082s). It did not need Git, tests,
  training configs, reports, matplotlib, httpx or the original source tree.
- Live Windows HTTP smoke passed (30.043s). Separate process termination/restart
  and repeat smoke passed (42.720s). The existing port-8000 process was not stopped;
  this milestone's server used 127.0.0.1:8017 and was cleaned up afterward.
- Edge smoke passed in 10.038s at all three requested sizes, exercising queue,
  graph 1/2/3 hops, expansion, address details, timeline, search, path highlights,
  zoom/pan and error handling. 27 page requests, zero external page requests and
  zero JS exceptions. The host initially blocked GPU/renderer operation; the
  successful temporary, localhost-only browser used `--no-sandbox --in-process-gpu`.
  This is not OS-level network isolation; normal application/browser settings
  were not changed. Verification browser instances were closed afterward.
- Known demo transaction/address and evaluation-selected 30-transaction/58-second
  sequence passed. 58 seconds is observation span, not runtime or a model claim.
- Git Bash syntax and negative startup/install/build guards passed. Git Bash does
  not establish Linux execution. pip check and git diff --check passed. Git emits
  existing autocrlf notices for the two modified Python scripts; no whitespace
  errors. Shell files have LF and archive executable modes.

## Remaining presentation gate

No usable Linux environment was available. Obtain matching Linux binary wheels
with CPython 3.13.14, complete offline install and load the unchanged trusted model,
then run [the clean-machine/network-disabled checklist](release_checklist.md).
Until that passes, the generated tar is a **preparation bundle**, not a complete
Linux offline distribution. The Python interpreter, venv support and browser are
OS prerequisites. Follow [README_OFFLINE.md](../README_OFFLINE.md).

The full Windows prototype is verified. The blocker to calling it a verified Linux
offline prototype is target Linux wheel/install/runtime/rehearsal evidence.

## Exact files intended for Git

New/modified source, docs and compact evidence only; no staging or commit performed.

- `.gitignore`
- `AGENTS.md`
- `PROJECT_CONTEXT.md`
- `README.md`
- `scripts/build_dashboard.py`
- `scripts/smoke_dashboard.py`
- `.gitattributes`
- `README_OFFLINE.md`
- `backend/requirements-offline-lock.txt`
- `backend/tests/test_release.py`
- `docs/release_checklist.md`
- `docs/release_verification.md`
- `install.sh`
- `release_manifest.json`
- `reports/release/browser.json`
- `reports/release/checks.json`
- `reports/release/http.json`
- `reports/release/relocated_runtime.json`
- `reports/release/restart.json`
- `reports/release/verification.json`
- `scripts/build_wheelhouse.sh`
- `scripts/release.py`
- `scripts/verify_runtime.py`
- `start.sh`
- `verify.sh`
