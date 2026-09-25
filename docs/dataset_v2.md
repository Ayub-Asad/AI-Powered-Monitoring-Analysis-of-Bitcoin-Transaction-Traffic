# Dataset schema v2 and assumptions

## Version and files

The original `data/btc_synthetic_dataset.csv` is preserved. Its SHA-256 is `d854ff1bccbdc40ed1989f31bf94fdbe976750e641be0ae27d322e697217bfad`.

The CLI defaults to v2; the existing `BitcoinDatasetGenerator` class and `--schema-version 1` retain legacy generation. V2 implementation is `BitcoinDatasetV2Generator` in `scripts/dataset_v2.py`. See README for exact regeneration commands.

Development: exactly 18,000 records, seed 42, 15,300 normal and 2,700 anomalous. Regression: exactly 1,000 records, 850 normal and 150 anomalous, seed 42. Each has CSV, JSONL, a ground-truth JSONL sidecar and a manifest containing schema version, seed, actual counts, scenario count, monetary/network conventions and SHA-256 hashes.

Schema version is recorded in the manifest, not as a model feature. Ingestion determines each row's allocation mode from the two amount fields: both absent/null is legacy; supplying either requires both valid arrays. Mixed legacy/v2 files are supported.

## Fields

| Field | Meaning and validation |
|---|---|
| timestamp | Observation time, normalized to timezone-aware UTC; ISO-8601 or epoch seconds/milliseconds accepted. Before genesis or more than one day into the future is rejected. Naive times warn and assume UTC. |
| src_ip, dst_ip | Synthetic observed peer addresses; valid IPv4/IPv6. Unspecified/multicast rejected; nonpublic addresses warn. No wallet ownership implication. |
| src_port, dst_port | Integer ports 1-65535. |
| txid | Unique synthetic identifier; 64 lowercase hexadecimal characters, not a blockchain transaction hash. |
| input_addresses, output_addresses | Ordered nonempty address arrays; repeated entries are preserved and warned about. Structural Bitcoin-like validation, not checksum verification. V2 forbids empty/null entries. |
| num_inputs, num_outputs | Entry counts, including repeated addresses. Derived if absent. Supplied invalid/mismatched v2 counts reject; legacy mismatch remains a warning with source count preserved. |
| input_amounts, output_amounts | Paired ordered arrays of BTC amounts aligned by index to the address arrays. Nonnegative whole-satoshi values; no null entries. Absent/null in legacy canonical rows. |
| amount_btc | V2: sum of ALL outputs, including change; strictly positive, at most 21 million BTC. Legacy source meaning is retained, not reinterpreted. |
| fee_btc | Nonnegative miner fee. Zero permitted. Legacy rounding to 8 decimals is retained except negative raw values are rejected before rounding. V2 requires whole-satoshi precision. |
| fee_rate_sat_vb | Nonnegative optional rate; bad/missing legacy or v2 optional value becomes null with a warning when invalid. V2 generator derives it from integer fee and estimated size, rounded to 2 decimals. |
| country, asn, asn_org | Reported/synthetic context for the observed source IP. Country has two-letter structural validation; ASN is a nonnegative 32-bit integer. No real GeoIP lookup. Optional bad values warn and become null. |
| label, anomaly_type | Evaluation only. Source files retain these fields; ingestion removes them into a separate ground_truth table keyed by txid. Never in canonical transactions or feature inputs. |
| source_row | Ingestion-added lineage, not a source dataset field and not a model feature. |

Source v2 files have 20 fields. Canonical tables have 19 columns: the 18 non-ground-truth fields plus source_row. The separate ingestion ground-truth table has txid, label and anomaly_type. The generator sidecar additionally contains scenario_id and actor_id; those are not canonical fields and never reach feature extraction.

## Serialization and monetary convention

All four array fields use JSON-encoded arrays inside CSV cells (standard CSV quoting), and actual arrays in JSON/JSONL. Legacy pipe-separated addresses remain accepted. JSON accepts an array of objects or a list under transactions/records/data; JSONL is one object per nonblank line.

For each non-coinbase v2 record:

```
amount_btc = sum(output_amounts)
sum(input_amounts) = sum(output_amounts) + fee_btc
len(input_addresses) = len(input_amounts) = num_inputs
len(output_addresses) = len(output_amounts) = num_outputs
```

Accounting and comparison use integer satoshis, with Decimal parsing at ingestion boundaries. Tolerance is zero satoshis: v2 sub-satoshi amounts are rejected rather than rounded. Floats are used only for external BTC-valued records and numerical feature tables. Zero individual allocations and zero fees are allowed, but total outputs must be positive. These cases are regression-tested, though typical generated allocations are positive.

Input allocations are consumed funding; output allocations are newly allocated values, including change. Repeated addresses retain separate entries and their allocations are summed for wallet flows. Input totals include fee funding and change-related effects and do not establish economic spending.

There is NO full UTXO ledger: no previous-output references, signatures, scripts, confirmation state, double-spend verification or ownership proof. General synthetic inputs are constructed to conserve value; this does not establish actual spendable UTXOs. Rapid and peeling chains do carry their preceding output value/address into the next input and deduct fees at each hop.

## Normal actors and network observations

V2 initializes 600 persistent actors with four reusable addresses each, unequal transaction weights, varied amount scales, activity windows and session centres across a 14-day horizon. Inputs reuse actor addresses; outputs include counterparties and change addresses. Occasional fresh addresses, multiple inputs/outputs, bursts, legitimate large transfers, dust-scale payments, unusual ports, and low/high fees create overlap with injected scenarios. Repeated input/output addresses can occur intentionally through sampling. They model multiple allocations, not extra transactions.

A shared pool of 280 observer IPs maps deterministically to synthetic country/private-ASN/organization tuples. ASN values are 64512-64791; organizations are explicitly named SYNTHETIC-NET-*. IPs are randomly sampled public-looking addresses and may coincide with real addresses; the mappings are NOT real geographic or routing information. Do not contact them or interpret their assigned countries as a lookup result. Source and destination peers are sampled from the same pool, independently of labels. Observing a wallet transaction at a peer does not establish control of that wallet.

V1's country-risk biases and category-specific time bands are not used in v2. All categories use the shared actor timing mechanism and observer pool. TXIDs use a seed/counter hash with the same construction for every class; addresses use the same synthetic format generator without label prefixes. Context, amounts and ports still carry scenario signals, but no claim of complete shortcut elimination or real-world representativeness is made.

## Injected scenarios

| Category | Development count | V2 implementation |
|---|---:|---|
| rapid_fire_layering | 540 | 18 complete 30-hop chains, 1-3 seconds between hops, carried funding minus fees, shared observer within each chain. |
| dust_attack | 405 | 5 complete 81-transaction bursts; persistent sender address, 1-3 recipient entries per transaction, 546-4000 satoshis per output, 0-2 seconds between observations. |
| high_value_single_hop | 405 | Large 5-600 BTC single-output transfers; normal traffic also includes this range. |
| peeling_chain | 405 | 17 complete chains of 23 or 24 transactions; peel 2-8% of remaining funding, carry distinct change output after fee deduction, 60-900 seconds between hops. |
| anomalous_port_usage | 405 | Nonstandard destination ports drawn from a pool also used by normal traffic; source port sometimes nonstandard. Network context, not proof of wrongdoing. |
| fee_anomaly | 270 | Low (0.05-2) or high (200-3000) sampled sat/vB rates, overlapping legitimate fee tails; integer fees, approximate shared size formula. |
| geo_velocity_impossible_travel | 270 | 135 complete pairs sharing a sender address, observations assigned different countries 30-300 seconds apart. This models a contextual inconsistency, not proof that a person travelled or owns either IP. |

Fees use the shared rough estimate `140 + 40*num_inputs + 30*num_outputs` vbytes, not serialized transaction sizes. Rapid/peeling fees are capped to conserve positive chain funding; this synthetic combination can remain a modelling shortcut.

Budgets use weights 20/15/15/15/15/10/10 percent with deterministic largest-remainder allocation. An odd geo remainder moves to the singleton high-value category; isolated single-row cluster budgets also move there. Cluster lengths are planned before generating rows; no output is truncated. Very small requested budgets may yield two-row clusters and omit categories. Zero requested records returns zero; negative/noninteger counts fail.

Regression category counts: rapid 30, dust 23, high-value 24, peeling 22, ports 22, fees 15, geo 14.

## Compatibility, diagnostics and limits

Duplicate TXIDs retain first occurrence and are classified as exact/conflicting; new arrays participate in fingerprints. Reports and API status codes retain their structure, with new validation error codes for invalid arrays, array lengths and monetary inconsistency. Canonical ordering remains timestamp/source-row stable. Optional v2 columns add to the canonical schema, so consumers that hardcode the old column count need updating.

The quality report compares labelled numerical quantiles and contextual frequency tables and reports best single-threshold balanced accuracy as a descriptive diagnostic. It is intentionally evaluation-only code outside feature engineering. The report checks anomaly-only contextual values with support at least five; this does not rule out rare or multivariate shortcuts. Labels describe injected scenarios, not verified criminality. No distribution is calibrated to real Bitcoin traffic.

Remaining limits: structural addresses only, no coinbase/addressless output support, no XML reader, no on-chain validation, no real GeoIP, no full actor balances. Complete clusters are synthetic and often more regular than real activity. Tests validate internal contracts, not blockchain authenticity.
