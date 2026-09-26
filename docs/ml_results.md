# Frozen synthetic ML baseline results — 2026-09-26

Configuration: `configs/ml_baseline.json`. All models and validation-selected thresholds were frozen before test labels were read. Seed 42 was the predefined reference; no model, feature, threshold or alert budget was changed after test evaluation. Complete numerical reports: `reports/ml/corpus_manifest.json`, `training_summary.json` and `evaluation.json`. Commands and methodology: [ML experiment guide](ml_anomaly_detection.md).

## Corpus audit

| Partition | Normal | Anomalous | Feature matrix | Wallets | Generating actors | Scenarios |
|---|---:|---:|---|---:|---:|---:|
| Train, seed 101 | 15,300 | 0 | 15,300 × 10 | 5,773 | 586 | 15,300 |
| Validation, seed 202 | 15,300 | 2,700 | 18,000 × 10 | 7,013 | 588 | 16,555 |
| Test, seed 303 | 15,300 | 2,700 | 18,000 × 10 | 6,952 | 587 | 16,555 |

Observed UTC periods: January 1 01:09:34–January 14 09:00:07; February 1 01:36:33–February 14 09:00:36; March 1 01:28:49–March 14 10:58:09, all in 2025. Every pair has **zero** transaction-ID, wallet-address, corpus-scoped actor/scenario and raw-scenario overlaps. All records ingest without rejection or duplication. The normal training count is established by generation with zero injected anomalies, without reading/filtering training labels. Validation and test counts are independently checked during evaluation.

Each mixed partition contains 540 rapid-layering, 405 dust, 405 high-value, 405 peeling, 405 unusual-port, 270 fee and 270 geo-velocity records. Scenarios are complete and remain in their corpus.

## Test metrics at frozen validation thresholds

| Model | Threshold | Precision | Recall | F1 | Average precision | PR-AUC (trapezoid) | ROC-AUC | FPR |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Isolation Forest 42 | 0.490957871 | 0.187902 | 0.552222 | 0.280395 | 0.190786 | 0.190485 | 0.591120 | 0.421176 |
| Isolation Forest 43 | 0.496210406 | 0.193929 | 0.522963 | 0.282938 | 0.187722 | 0.187446 | 0.583957 | 0.383595 |
| Isolation Forest 44 | 0.496811952 | 0.201677 | 0.543333 | 0.294165 | 0.196686 | 0.196412 | 0.604915 | 0.379542 |
| Robust-deviation heuristic | 1.433530268 | 0.217083 | 0.679630 | 0.329059 | 0.203687 | 0.206158 | 0.620576 | 0.432549 |

| Model | TN | FP | FN | TP | Threshold alerts |
|---|---:|---:|---:|---:|---:|
| IF 42 | 8,856 | 6,444 | 1,209 | 1,491 | 7,935 |
| IF 43 | 9,431 | 5,869 | 1,288 | 1,412 | 7,281 |
| IF 44 | 9,493 | 5,807 | 1,233 | 1,467 | 7,274 |
| Heuristic | 8,682 | 6,618 | 865 | 1,835 | 8,453 |

Validation F1 was 0.307014, 0.306664 and 0.313749 for seeds 42/43/44, and 0.333715 for the heuristic. The F1 objective selects many alerts and high FPR; this is not an approved deployment operating point. The heuristic outperforms all three forests on test F1 and ROC-AUC. No replacement of the predefined reference or retuning was made.

| Metric across IF seeds | Mean | Population SD | Minimum | Maximum |
|---|---:|---:|---:|---:|
| Precision | 0.194503 | 0.005638 | 0.187902 | 0.201677 |
| Recall | 0.539506 | 0.012248 | 0.522963 | 0.552222 |
| F1 | 0.285832 | 0.005983 | 0.280395 | 0.294165 |
| Average precision | 0.191731 | 0.003720 | 0.187722 | 0.196686 |
| PR-AUC | 0.191448 | 0.003723 | 0.187446 | 0.196412 |
| ROC-AUC | 0.593331 | 0.008698 | 0.583957 | 0.604915 |
| FPR | 0.394771 | 0.018744 | 0.379542 | 0.421176 |

## Per-category test recall

| Category | Transactions / scenarios | IF 42 | IF 43 | IF 44 | Heuristic |
|---|---|---:|---:|---:|---:|
| Rapid-fire layering | 540 / 18 | 19.63% | 19.07% | 19.26% | 17.22% |
| Dust | 405 / 5 | 98.02% | 91.60% | 97.28% | 100.00% |
| High-value | 405 / 405 | 87.16% | 84.69% | 89.63% | 100.00% |
| Peeling | 405 / 17 | 27.65% | 24.44% | 26.91% | 91.85% |
| Unusual ports | 405 / 405 | 44.44% | 41.98% | 41.73% | 46.91% |
| Fee anomalies | 270 / 270 | 88.89% | 84.07% | 85.93% | 100.00% |
| Geo-velocity | 270 / 135 | 38.15% | 36.67% | 35.56% | 37.04% |

High recall in some categories accompanies very high false-positive rates. Port/geo recall does not demonstrate detection of port/travel mechanisms because those features are excluded. Dust has only five independent bursts, so hundreds of rows do not represent hundreds of independent scenarios. These are transaction recall measures, not wallet or scenario-level classification results.

## Fixed alert-budget precision

Each cell gives precision and true positives / actual alerts. Ranking uses score descending and TXID ascending for ties. These budgets were fixed before evaluation.

| Model | Top 1%: 180 alerts | Top 5%: 900 alerts | Top 10%: 1,800 alerts |
|---|---|---|---|
| IF 42 | 27.78% (50/180) | 18.44% (166/900) | 20.89% (376/1,800) |
| IF 43 | 26.67% (48/180) | 19.56% (176/900) | 19.83% (357/1,800) |
| IF 44 | 27.22% (49/180) | 20.67% (186/900) | 21.22% (382/1,800) |
| Heuristic | 30.00% (54/180) | 20.33% (183/900) | 27.11% (488/1,800) |

Synthetic test prevalence is 15%. Precision values cannot be carried over to deployment with a different prevalence. Scores are not calibrated probabilities or evidence of illegal activity.

## Measured execution

| Stage | Seconds |
|---|---:|
| Generate/serialize train | 8.502 |
| Generate/serialize validation | 7.023 |
| Generate/serialize test | 7.836 |
| Training preparation: all transaction/grouping ingestion and audit | 18.116 |
| Fit IF 42 / 43 / 44 | 1.145 / 1.434 / 0.922 |
| Fit heuristic, shared preprocessing already fitted | 0.017 |
| Score validation IF 42 / 43 / 44 | 0.584 / 0.615 / 0.489 |
| Calibrate IF 42 / 43 / 44 | 0.0058 / 0.0054 / 0.0051 |
| Score validation / calibrate heuristic | 0.0137 / 0.0029 |
| Training workflow before final freeze/report writes | 25.783 |
| Score test IF 42 / 43 / 44 / heuristic | 0.532 / 0.490 / 0.503 / 0.023 |
| Test evaluation including loading, ingestion and plots | 31.872 |

These are measured runs on this environment, not benchmarks. Initial dependency/ML imports and the first Matplotlib font-cache build contributed startup overhead. Artifact manifests pin Python and numerical dependencies and record source hashes because the work is intentionally uncommitted.

## Validation record

Focused phases: split checks 7 passed (30.60s during installation); preprocessing/scoring/evaluation 26 passed (37.82s, initially including an overflow-fixture warning subsequently handled); artifact/lifecycle checks 36 passed (19.06s); final combined ML checks 55 passed (14.56s), no warnings. An early collection attempt ran before dependency installation completed and failed two module imports; rerunning after installation passed. No tests were weakened or skipped to hide failures. Full-suite and scoring-smoke results are recorded in the milestone validation document and compact validation report.

Remaining work is separate from this milestone: real-data validation, deployment alert policy, and causal sequence/wallet features with their own frozen evaluation protocol. The present results do not justify an operational crime-detection claim.
