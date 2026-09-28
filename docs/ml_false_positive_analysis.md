# Validation false-positive analysis

Population: reused February 2025 validation corpus, seed 202; 15,300 synthetic normal and 2,700 injected anomalous transactions. These analyses were reviewed before the approved seed-405 final generation. They did not change the approved selection rule, generator, labels or 10-feature input schema. Complete grouped summaries for all seven models, all 10 features, score quantiles and examples are in `reports/ml/tuning/run-001/false_positives.json`.

## Alert-policy comparison

| Model, seed 42 where applicable | F1-threshold false alerts | F1-threshold FPR | Top-1% true / false alerts | Top-1% precision | Top-1% recall |
|---|---:|---:|---:|---:|---:|
| Frozen IF | 6,327 | 41.35% | 50 / 130 | 27.78% | 1.85% |
| Tuned IF | 4,798 | 31.36% | 51 / 129 | 28.33% | 1.89% |
| Frozen heuristic | 6,752 | 44.13% | 49 / 131 | 27.22% | 1.81% |

The tuned F1 threshold reduces false alerts on this development population. At the primary review budget, however, the reference model gains only one true alert. Neither result establishes an adequate operational detector. The selected configuration's three-seed mean top-1% precision is 28.52%, with 1.90% recall and 51.33 true / 128.67 false alerts.

## Where normal records rank highly

For tuned seed 42 at top 1%, 102 of 129 false positives (79.1%) have total output amount at most 0.00004 BTC. Separately, 108 (83.7%) have fees above 0.001 BTC; these groups overlap and should not be added. Within those normal populations, selection rates are 9.32% (102/1,095 tiny-amount normals) and 7.88% (108/1,371 high-fee normals).

At the much broader F1 threshold, 1,085/1,095 tiny-amount normal transactions are flagged (99.09%), as are 1,348/1,371 high-fee normal transactions (98.32%). The normal generator deliberately includes small amounts and extreme fees. A plausible hypothesis is that rare combinations of otherwise permitted normal values receive strong isolation scores, especially through fee-to-amount ratio. This is an observational association, not demonstrated feature attribution or causality.

| Feature median, tuned top-1% policy | False positives | Correctly unflagged normals |
|---|---:|---:|
| Amount BTC, including change | 0.00002455 | 0.07196413 |
| Fee BTC | 0.00493801 | 0.00008857 |
| Fee rate sat/vB | 1,856.00 | 33.63 |
| Fee / amount ratio | 157.49 | 0.001118 |
| Prior global transactions in 60 seconds | 1 | 1 |

Input/output shape also varies: top-1% normal selection is 1.38% for three inputs versus 0.69% for one input; it is 1.65% for one output versus 0.59% for two outputs. These conditional rates do not control for correlated monetary or timing features.

At the F1 threshold, UTC hour 0 has 357/620 normal records flagged (57.58%), and hour 4 has 302/597 (50.59%). At the exact top 1%, hour 2 has 14/596 (2.35%). Calendar and night features may contribute to these patterns, but generator scheduling and correlated amounts could also explain them. No causal conclusion or post-hoc feature removal was made.

## Historical intensity and score groups

Intensity counts globally observed transactions in `[t-60 seconds,t)`, excluding every transaction tied at `t`. It is a diagnostic only, not a wallet feature or model input. At the F1 threshold, false positives and true negatives both have median 1 and 75th percentile 3; their 95th percentiles are 8 and 9. At top 1%, the corresponding false-positive/true-negative 95th percentiles are 5/9. These summaries do not show a simple concentration of false positives in the busiest observed moments.

Score bins use validation quantiles, retaining tied scores in the same bin. For tuned seed 42 the highest displayed bin, approximately `(0.636, 0.729]`, contains the 129 normal top-1% false positives. Its 100% flag rate is expected from defining the bin using the same ranking, not an independent explanatory finding. Exact quantile edges and per-bin denominators are retained in JSON.

## Representative synthetic examples

Highest-score normal examples for tuned seed 42, using local row aliases instead of addresses or TXIDs:

| Alias | Amount BTC | Fee BTC | Inputs / outputs | Prior 60s count | Score |
|---|---:|---:|---:|---:|---:|
| validation-row-01271 | 0.00000590 | 0.00545296 | 3 / 1 | 1 | 0.728508 |
| validation-row-03191 | 0.00002861 | 0.00627935 | 3 / 1 | 1 | 0.718397 |
| validation-row-09792 | 0.00001605 | 0.00452153 | 2 / 1 | 0 | 0.704013 |

Large fees relative to tiny outputs are valid under the synthetic monetary conservation rules, but their real-world frequency has not been established. These examples are not evidence about real wallets or suspicious owners. No records were removed, relabeled or modified. Final-test false-positive exploration is intentionally outside this validation-only report.
