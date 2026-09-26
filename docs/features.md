# Feature definitions and usage

## Input and output contract

`extract_features(IngestionResult.transactions, FeatureConfig(...))` accepts canonical UTC transactions only. It rejects duplicate TXIDs and frames containing label, anomaly_type, ground_truth, actor_id or scenario_id. Ingestion performs deduplication first. Feature code never reads the separate ground-truth table.

Outputs are deterministic: transaction rows sort by timestamp/txid; wallet rows sort by wallet_address. This ordering is independent of input row order. TXIDs and wallet addresses are stable join identifiers, never numerical ML inputs. No hashing/encoding of identifiers is supplied to ML.

`transaction_features`: txid plus 10 default behavioural ML features (11 columns).
`wallet_features`: wallet_address, 17 default behavioural ML features, max_tx_in_window and two availability flags (21 columns).
`transaction_context`: txid plus 9 contextual/lineage fields (10 columns).
`wallet_context`: wallet_address plus four contextual counts (5 columns).

The lists are executable constants in `app/features/schema.py` and exported in `feature_manifest.json`. `ml_ready_frame(table, kind)` selects only the named behavioural columns and rejects NaN/infinite values. It does not invent imputation, scaling or training. Optional fee rates and legacy flows can be unavailable; a later ML milestone must choose a documented missing-value policy.

## Transaction features (default ML list)

| Feature | Definition |
|---|---|
| amount_btc | Canonical transaction total. V2 includes change; legacy source meaning is retained. |
| fee_btc | Canonical miner fee. |
| fee_rate_sat_vb | Canonical optional approximate sat/vB rate; null if unknown. |
| num_inputs, num_outputs | Canonical entry counts, not unique wallet counts. Legacy source mismatches are retained by ingestion. |
| fee_to_amount_ratio | fee_btc / amount_btc; total is strictly positive, zero fee gives zero. |
| input_output_count_ratio | num_inputs / num_outputs; zero legacy output count gives unavailable (NaN), never infinity. |
| hour_of_day_utc | UTC hour 0-23. |
| day_of_week_utc | UTC weekday, Monday=0 through Sunday=6. |
| is_night_utc | 1 for UTC hours 00:00 through 05:59:59, otherwise 0; not local-time night. |

These are descriptive observations; high values, large ratios or night activity are not themselves evidence of wrongdoing.

## Wallet features (default ML list)

A wallet is an address string, not a verified person/entity. For every transaction involving an address, count one activity observation even if it appears repeatedly or on both sides. A wallet on both sides contributes once to each directional count and once to the total count. Allocations of repeated entries are summed.

| Feature | Definition |
|---|---|
| transaction_count | Number of distinct involving transactions. |
| incoming_transaction_count | Number of transactions containing the wallet in outputs. |
| outgoing_transaction_count | Number containing the wallet in inputs. |
| total_received_btc | Sum of all allocated outputs for this wallet, including change and repeated entries. Unavailable if any incoming observation lacks amounts. Zero if no incoming observations. |
| total_sent_btc | Sum of all allocated consumed inputs for this wallet. Unavailable if any outgoing observation lacks amounts. Zero if no outgoing observations. Includes funding for fees and change; not net economic spending. |
| average_transaction_amount | Mean of amount_btc over distinct involving transactions. This is whole-transaction size, NOT the wallet's individual received/sent allocation. |
| median_transaction_amount | Median of those same whole-transaction totals. |
| transaction_amount_std | Population standard deviation (ddof=0) of those totals; zero for one observation. |
| min_transaction_amount, max_transaction_amount | Minimum/maximum whole-transaction totals over those observations. |
| unique_counterparties | Size of union of distinct co-occurring opposite-side addresses, excluding self. |
| fan_in | Distinct input-side counterparties across transactions where the wallet is an output; self excluded. |
| fan_out | Distinct output-side counterparties across transactions where the wallet is an input; self excluded. |
| active_duration_seconds | Last involving timestamp minus first, in seconds. Zero for singleton or all-tied times. |
| mean_inter_transaction_seconds | Mean adjacent timestamp gap after sorting distinct transactions; ties contribute zero. Singleton gives zero by convention. |
| median_inter_transaction_seconds | Median of those gaps; singleton gives zero. |
| max_tx_in_60s | Largest number of distinct involving transactions in any closed window [t-60 seconds, t]. Exact 60-second boundaries and tied timestamps are included. |

Counterparties are co-occurrence relationships, not inferred allocation links: multi-input/output records do not uniquely identify which input funds which output. No graph analysis or ownership clustering is performed.

## Additional roles

- **Configurable behavioural feature:** max_tx_in_window uses FeatureConfig.burst_window_seconds, default BURST_WINDOW_SECONDS=60. max_tx_in_60s always retains its literal 60-second definition. At the default these coincide, so max_tx_in_window is excluded from the default ML list to avoid a duplicate column. Window configuration is saved in the manifest.
- **Availability metadata:** incoming_amounts_available and outgoing_amounts_available indicate complete per-direction allocation coverage. They are not default behavioural ML inputs; using them could expose data-source/version differences.
- **Transaction investigative context:** timestamp, src_ip, dst_ip, src_port, dst_port, country, asn, asn_org, source_row, joined by txid. source_row is lineage; raw addresses/IDs are never numerical features.
- **Wallet investigative context:** unique_observed_src_ips, unique_observed_dst_ips, unique_observed_countries, unique_observed_asns over involving transactions. Missing optional context is excluded from its distinct count. These statistics describe observations, not wallet ownership or travel.
- **Identifiers:** txid in transaction tables and wallet_address in wallet tables. No actor_id or scenario_id is used by extraction.
- **Unavailable features:** exact directional flow totals when relevant v1 records lack arrays; optional unknown fee_rate_sat_vb; undefined legacy count ratios. Missingness is preserved, never silently replaced with zero.
- **Estimated features:** none. No estimated per-address flows are generated.

## Temporal and evaluation limits

The implemented [ML baseline](ml_anomaly_detection.md) uses only the ordered 10 transaction features, with its own strict schema, train-only imputation and fixed log transforms. It preserves `ml_ready_frame` unchanged and does not consume the descriptive wallet tables. Labels and grouping metadata remain outside numerical preprocessing and fitting.

Wallet aggregates cover the entire supplied observation window. They are suitable for offline descriptive analysis; they are not point-in-time online predictions. Historical scoring must extract from only information available at the scoring cutoff. New train/test periods must recompute aggregates independently and handle overlapping actors/scenarios deliberately. Reused wallet addresses can otherwise cause split leakage even though explicit labels never enter features.

Synthetic labels are transaction/scenario-level. Wallets may participate in both normal and anomalous transactions; no wallet-level label is invented. A later evaluation milestone must define its wallet target and aggregation policy. Freeze splits before selecting/scaling features or tuning model thresholds. Port and geo scenarios may need separate contextual investigation rather than default behavioural detection.

V1 and v2 amount_btc semantics may differ, particularly old peeling records; do not silently compare their exact economic meaning. Float feature statistics have normal floating-point precision; monetary conservation and allocation totals are computed in integer satoshis before conversion to output BTC values.
