# Bitcoin graph investigation

The offline graph milestone is implemented. The ML baseline and bounded tuning
are complete and remain frozen. API/dashboard integration and offline prototype
packaging are next; there are no new HTTP routes or frontend in this milestone.

Transaction-only anomaly scores miss many synthetic layering and peeling
sequences. The graph lets an investigator inspect address-linked activity,
time order, values and existing scores together. It does not improve or retrain
the model, infer ownership, establish criminality or prove UTXO spends.

## Representation and accounting

`backend/app/graph/` uses indexed Python dictionaries and adjacency lists. No
new dependency, graph database, network service or internet request is needed.
`build_graph(IngestionResult.transactions, scores=None)` consumes canonical data;
duplicate TXIDs and evaluation fields are rejected. The graph has two node types:

- `transaction:TXID`: timestamp, source counts, fee/value in BTC and integer
  satoshis, allocation availability, score/threshold/flag/model version, context.
- `address:ADDRESS`: the observed address, not an inferred actor or wallet owner.
  Full-graph degree, incoming/outgoing relationship counts, unique connected
  transaction count, first/last observations, scored/flagged counts and maximum
  attached score are descriptive aggregates.

Directed input edges run address -> transaction; output edges run transaction ->
address. Multiple inputs do not establish which input funded which output, so
there are no direct sender-address -> recipient-address edges. Input amounts
are contributed allocations, not attributed payments to a particular recipient.
Repeated allocations to an address are summed in integer satoshis into one edge
per transaction/address/direction; `allocation_count` preserves multiplicity.
An address appearing as both input and change has two relationships but counts
the transaction once. Edge IDs are deterministic JSON tuples of type/TXID/address.

V2 totals include change; inputs equal outputs plus fees. Legacy allocation
amounts remain null, with explicit completeness flags and separate known-value
subtotals. Legacy declared input/output counts retain source meaning; observed
unique-address counts and degree are separate. No amounts are silently estimated.
Whole-graph address statistics describe the loaded observation window, not a
balance, historical causal feature or ML input. Components are weakly connected;
component size counts both transaction and address nodes.

## Investigation interface

Import public operations from `app.graph` when running from `backend/`:

```python
from app.ingestion import ingest_file
from app.graph import (
    build_graph, transaction_lookup, address_lookup, neighbourhood,
    suspicious_neighbourhood, trace_sequence, timeline, search_transactions,
    TransactionFilter, Limits, dumps,
)
from app.graph.integration import score_with_artifact

canonical = ingest_file('../data/v2/development.csv').transactions
scores = score_with_artifact(canonical, '../artifacts/ml/tuning/run-001/tuned-42')
graph = build_graph(canonical, scores)  # omit scores for an unscored investigation
txid = canonical.txid.iloc[0]
address = canonical.input_addresses.iloc[0][0]
immediate = transaction_lookup(graph, txid)
address_view = address_lookup(graph, address)
nearby = neighbourhood(graph, 'transaction:' + txid, hops=3,
                       limits=Limits(max_nodes=250, max_edges=500, max_expansions=10000))
alerts = search_transactions(graph, TransactionFilter(flagged_only=True), limit=20)
seed = alerts['nodes'][0]['attributes']['txid']
investigation = suspicious_neighbourhood(graph, seed)
ordered = timeline(graph, 'address:' + address)
json_text = dumps(investigation)
```

`transaction_lookup` and `address_lookup` return a bounded immediate
neighbourhood. `neighbourhood` explores undirected connectivity in deterministic
edge order; one hop means one bipartite edge. Transaction -> address -> transaction
requires two hops. Defaults are 250 nodes, 500 edges and 10,000 relationship
inspections. Limits are configurable. Early termination reports `truncated` and
`truncation_reason`; results never contain dangling edges. An exhausted limit
can omit relationships between already included nodes: this is a bounded
exploration, not necessarily an induced subgraph. Global node statistics can
therefore exceed the size of the displayed neighbourhood.

`TransactionFilter` supports `flagged_only`, `min_anomaly_score`, inclusive UTC
`start`/`end` and `min_amount_satoshis`. Neighbourhood filters apply to encountered
transactions; the selected seed is retained for context even if it does not
match. Nonmatching transactions block further expansion through them. Timeline
shares those bounds and sorts returned transactions by timestamp then ID.
Search scans transaction nodes and returns a time-ordered page (maximum page
size 10,000), with total matches and next offset; JSON node arrays remain sorted
by stable ID. Use timeline for chronological presentation.

`find_path(graph, source, target)` returns ordered node/edge IDs, defaulting to
directed, strictly increasing transaction times with a 12-edge maximum.
`trace_sequence` adds transaction timestamps, amounts, scores and elapsed-time
explanation. For example:

```python
sequence = trace_sequence(graph, 'transaction:' + first_txid,
                          'transaction:' + last_txid, max_hops=20)
```

These are shortest address-linked paths within the search budget. Equal-time
transactions are excluded in chronological mode because ordering is unknown.
`find_path(..., chronological=False)` permits structural directed paths;
also set `directed=False` to explore undirected connectivity. Path search budgets
count visited states and inspected relationships; a state includes previous
transaction time so address reuse does not suppress an earlier valid path.
`found=False` means no path found within the specified hop/search bounds, not
proof of disconnection. `max_hops` is capped at 100. Flags do not restrict paths.

## ML, network context and provenance

Scores join by TXID, never row position. Partial scores are supported; unknown
TXIDs, duplicate scores, nonfinite values and flags inconsistent with
`score >= threshold` are rejected. A score table represents one model selection
per transaction; switch tables to compare models. Unscored values are null,
including `flagged`, rather than false. Scores are not probabilities.

`score_with_artifact` uses the existing strict ordered ten-feature interface,
existing artifact checksum/environment checks, frozen preprocessing and scoring
function. The version identifier includes artifact directory name and manifest
SHA-256. The caller must supply a trusted local artifact. There is no fitting,
calibration, label access or tuning. Optional missing ML features retain the
existing training-median preprocessing policy. Saved scores can instead be
passed directly using the existing `score_transactions` DataFrame contract.

Canonical source/destination IPs and ports, country, ASN and organisation remain
transaction context with source-row provenance. They are reported/synthetic
observations, not blockchain-native properties, actual geolocation or ownership
evidence. Missing fields serialize to null. Separate IP nodes would suggest
relationships stronger than the current single-observation schema warrants,
so this milestone does not create them. The caller retains the source file/upload
identity associated with the in-memory graph; `source_row` is relative to it.

Ground truth, anomaly categories, actor IDs and scenario IDs are excluded from
graph construction and traversal, including display payloads. Only
`scripts/verify_graph.py` reads the existing development scenario sidecar after
construction/scoring, to check consecutive pairs and end-to-end paths in one
existing layering and one peeling example. These examples are explicitly
evaluation-selected, not discoveries by the model. Handwritten unit fixtures
also test branching, change outputs, backward time and ties. Poor frozen ML
category results are unchanged.

Development verification reconstructs all adjacent pairs in the selected
30-transaction layering and 24-transaction peeling scenarios. The complete
layering path is found. The peeling end-to-end search hits the configured
2,000-state limit in dense shared-address activity; its three-transaction preview
is found. This limitation is retained in the report, not treated as proof of
disconnection. Investigators can follow bounded segments or explicitly increase
their search budget.

## Dashboard JSON and semantic styling

Every operation returns JSON-native `schema_version: bitcoin-investigation-v1`,
`nodes`, `edges`, `summary`, `truncated` and `truncation_reason`. Nodes include
namespaced ID, type, shortened label, UTC timestamp (transaction), score, flag,
attributes, factual reasons and visual semantics. Transaction nodes additionally
include threshold and model version. Edges include ID, source, target, type,
nullable BTC/satoshi amount, allocation count and path styling metadata.
Summary counts cover returned nodes/edges, including scored and flagged counts.
`dumps` sorts keys and rejects nonfinite JSON values; responses are detached
copies, safe to pass to FastAPI. The graph itself should be treated as read-only
after construction.

Styling is centralized in `serialization.py`: `transaction_normal`,
`transaction_flagged`, `transaction_unscored`, `address`, selection and path
highlight. `network_context` is reserved for contextual UI panels. There is no
`transaction_high_risk` classification because no validated high-risk threshold
exists. A future dark navy/charcoal dashboard can use cyan for ordinary edges,
amber for ML flags, muted gray for unscored/context, and directional arrows.
No backend color palette or stronger red risk tier is inferred. Render labels
as text, not HTML. Explanations report observed counts and threshold comparisons,
never ownership or criminality claims.

## Verification and reproduction

From the repository root, with the existing venv (no generation or training):

```powershell
Push-Location backend
..\venv\Scripts\python.exe -B -m pytest tests/test_graph.py -q -p no:cacheprovider
..\venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider
..\venv\Scripts\python.exe -B -m app.graph ../data/v2/development.csv --hops 3
..\venv\Scripts\python.exe -B -m app.graph ../data/v2/development.csv --artifact ../artifacts/ml/tuning/run-001/tuned-42 --hops 3
Pop-Location
.\venv\Scripts\python.exe -B scripts/verify_graph.py --out artifacts/graph/verification-repeat.json
```

CLI `--entity transaction:TXID` or `--entity address:ADDRESS` selects a seed;
`--out ../artifacts/graph/example.json` exports only a bounded neighbourhood and
refuses overwrite. Verification also refuses overwrite. Generated graph files
belong in ignored `artifacts/graph/`. The compact measured report is
`reports/graph/verification.json`; test results are in `reports/graph/tests.json`.

On Linux, use the already installed environment's `python -B` in place of the
Windows executable paths; all Python paths/operations are portable. No runtime
internet, CDN, GeoIP service, graph service or database is required. Linux itself
was not executed during the Windows verification.

The in-memory prototype loads the complete canonical dataset and scores.
Pagination/service lifecycle, authentication, upload-to-graph API wiring and
dashboard rendering remain the next milestone. Real-chain adapters still need
coinbase/addressless-output support and UTXO references before claiming actual
fund tracing. No new ML metric, centrality risk score or ownership clustering is
introduced.

## Measured milestone result

Complete suite: **228 passed + 75 passing subtests**, zero failures/skips,
one known Starlette/httpx warning, **128.93s**. Graph suite: **29 passed**,
zero failures/skips, **1.59s**. `pip check` and `git diff --check` passed.
All **248** inventoried pre-existing protected data/config/feature/ingestion/ML
source, model and report files retain their SHA-256 hashes.

Development graph: **25,059 nodes** (18,000 transactions + 7,059 addresses),
**60,836 edges**. Final verification measured unscored construction **6.737s**,
scored construction **5.015s**, frozen inference **3.604s**, transaction lookup
**0.286ms**, address lookup **1.183ms**, three-hop traversal **16.835ms** and
suspicious neighbourhood **18.223ms**. The representative three-hop result has
245 nodes and 370 edges without truncation; a 10-node cap returns 10 nodes and
9 edges with truncation. Measurements are single-run observations, not latency
benchmarks. All 18,000 transactions have scores; 6,153 exceed or meet the frozen
threshold. This is not a held-out accuracy result.
