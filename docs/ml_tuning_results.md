# Frozen tuning and fresh final-test results - 2026-09-28

The approved search completed 12 configurations x seeds 42/43/44 (36 production fits, 171.49s). Selected: **200 trees, max_samples 1024, max_features 0.8, bootstrap false**. These exact fitted models, preprocessing, thresholds and policies remained unchanged for the final evaluation. No ensemble or post-test selection was performed.

Primary objective: mean validation precision at exact top 1%, with mean recall >=1% as a feasibility check only; ties use mean validation F1, then canonical configuration ordering. The 1% recall condition is not evidence of adequate detection.

## Historical benchmark: seed 303

The original March 2025 test was already inspected and remains a historical reference. Saved predictions reproduced all original metrics during the audit; original artifacts/reports remain unchanged. Do not compare different populations as evidence of improvement.

| Model | Precision | Recall | F1 | FPR | AP | PR-AUC | ROC-AUC |
|---|---:|---:|---:|---:|---:|---:|---:|
| Original IF 42 | 18.79% | 55.22% | 0.2804 | 42.12% | 0.1908 | 0.1905 | 0.5911 |
| Original heuristic | 21.71% | 67.96% | 0.3291 | 43.25% | 0.2037 | 0.2062 | 0.6206 |

## Validation-driven tuning: seed 202

The reused February validation set selected the models and thresholds. The selected three-seed mean top-1% precision was 28.52%, recall 1.90%, with 51.33 true and 128.67 false alerts among 180 reviews. Frozen original IF mean top-1% precision was 27.04%. Mean tuned validation F1 was 0.319837. This population is development data, not an unbiased improvement estimate.

| Reference model | Validation F1 | FPR | Top-1% precision | Top-1% recall | True / false alerts |
|---|---:|---:|---:|---:|---:|
| Original IF 42 | 0.307014 | 41.35% | 27.78% | 1.85% | 50 / 130 |
| Tuned IF 42 | 0.323345 | 31.36% | 28.33% | 1.89% | 51 / 129 |
| Heuristic | 0.333715 | 44.13% | 27.22% | 1.81% | 49 / 131 |

## Approved seed change and independence audit

Early small regression fixtures used seed 404 (60 normal / 20 anomalous rows), potentially exposing its first 60 production normal records. No fixture metrics influenced model selection. The user explicitly approved replacing 404 with **405**, keeping the April window and 15,300 normal / 2,700 anomalous counts. The original freeze and seed-404 protocol remain intact; `configs/ml_final_405.json` and `seed_change.json` record the additive amendment. Future generated fixtures use 9404; amendment tests mock literal records and never instantiate the seed-405 generator.

Both the model freeze and the seed-change reservation were verified before generation. The fixture inventory was sealed first. Final generation, identity/chronology auditing, all seven model scores and only then final-label access occurred in that order. The production final command was executed once; no retuning, refitting, recalibration or seed/budget selection followed.

Final corpus: **18,000 transactions, 7,003 wallets, 591 scoped generating actors and 16,555 complete scenarios**. Observed UTC period: **April 1 00:46:07 to April 14 11:21:47, 2025**. It is chronologically after training, validation, the original test and tracked v1/v2 datasets.

All **21 reference populations** had zero TXID, wallet, scoped actor/scenario and raw scenario overlaps where those identifiers exist. The inventory covered the original partitions, tracked v1/v2, 68 retained transaction files (four distinct retained identity sets), reconstructed known fixtures including deleted seed-404 examples, and a conservative handwritten-identity superset.

April regression fixtures intentionally share calendar time with the final corpus; three such comparisons report time overlap and do not serve as chronological train/test partitions. Legacy fixtures lack actor/scenario metadata, so those checks are unavailable rather than evidence of real-world identity separation. Local actor names are corpus-scoped; wallet and unscoped scenario hashes provide additional checks. Unknown external fixtures cannot be audited.

## Fresh seed-405 metrics at frozen F1 thresholds

These threshold flags use each model's previously frozen validation-F1 cutoff, not a fixed review count. AP is average precision; PR-AUC is trapezoidal.

| Model | Precision | Recall | F1 | FPR | AP | PR-AUC | ROC-AUC |
|---|---:|---:|---:|---:|---:|---:|---:|
| Original IF 42 | 19.31% | 56.07% | 0.287287 | 41.35% | 0.195371 | 0.195038 | 0.590994 |
| Original IF 43 | 19.47% | 51.67% | 0.282789 | 37.72% | 0.194278 | 0.193953 | 0.583256 |
| Original IF 44 | 19.98% | 53.67% | 0.291227 | 37.92% | 0.199136 | 0.198829 | 0.599119 |
| Tuned IF 42 | 21.44% | 49.41% | 0.299036 | 31.95% | 0.207854 | 0.207499 | 0.610277 |
| Tuned IF 43 | 20.60% | 50.37% | 0.292410 | 34.26% | 0.204386 | 0.204046 | 0.605630 |
| Tuned IF 44 | 20.50% | 55.07% | 0.298774 | 37.69% | 0.205217 | 0.204889 | 0.604769 |
| Heuristic | 22.00% | 69.96% | 0.334721 | 43.78% | 0.199924 | 0.202384 | 0.616506 |

| Model | Frozen threshold | TN | FP | FN | TP | Alerts | False alerts / 1,000 normal |
|---|---:|---:|---:|---:|---:|---:|---:|
| Original IF 42 | 0.490957871 | 8974 | 6326 | 1186 | 1514 | 7840 | 413.46 |
| Original IF 43 | 0.496210406 | 9529 | 5771 | 1305 | 1395 | 7166 | 377.19 |
| Original IF 44 | 0.496811952 | 9498 | 5802 | 1251 | 1449 | 7251 | 379.22 |
| Tuned IF 42 | 0.497773139 | 10412 | 4888 | 1366 | 1334 | 6222 | 319.48 |
| Tuned IF 43 | 0.491232697 | 10058 | 5242 | 1340 | 1360 | 6602 | 342.61 |
| Tuned IF 44 | 0.487986855 | 9533 | 5767 | 1213 | 1487 | 7254 | 376.93 |
| Heuristic | 1.433530268 | 8602 | 6698 | 811 | 1889 | 8587 | 437.78 |

## Seed variation on the same final population

Means and population standard deviations across fixed seeds 42/43/44. These are model-seed variations, not confidence intervals.

| Metric | Original IF mean +/- SD | Tuned IF mean +/- SD |
|---|---:|---:|
| precision | 0.195872 +/- 0.002873 | 0.208463 +/- 0.004219 |
| recall | 0.538025 +/- 0.018019 | 0.516173 +/- 0.024757 |
| f1 | 0.287101 +/- 0.003447 | 0.296740 +/- 0.003064 |
| false_positive_rate | 0.389956 +/- 0.016643 | 0.346340 +/- 0.023602 |
| average_precision | 0.196261 +/- 0.002081 | 0.205819 +/- 0.001478 |
| pr_auc_trapezoidal | 0.195940 +/- 0.002090 | 0.205478 +/- 0.001470 |
| roc_auc | 0.591123 +/- 0.006476 | 0.606892 +/- 0.002419 |

## Exact final review budgets

Ranked alerts use ceil(N x budget), descending score, then ascending TXID. They may split tied scores. Recall below is among all 2,700 injected anomalies; counts are true and false alerts. This is separate from every threshold-based flag count.

| Model | Budget | Reviews | True | False | Precision | Recall | False alerts / 1,000 normal |
|---|---:|---:|---:|---:|---:|---:|---:|
| Original IF 42 | 1% | 180 | 50 | 130 | 27.78% | 1.85% | 8.50 |
| Original IF 42 | 2% | 360 | 87 | 273 | 24.17% | 3.22% | 17.84 |
| Original IF 42 | 5% | 900 | 188 | 712 | 20.89% | 6.96% | 46.54 |
| Original IF 42 | 10% | 1800 | 393 | 1407 | 21.83% | 14.56% | 91.96 |
| Original IF 43 | 1% | 180 | 49 | 131 | 27.22% | 1.81% | 8.56 |
| Original IF 43 | 2% | 360 | 86 | 274 | 23.89% | 3.19% | 17.91 |
| Original IF 43 | 5% | 900 | 184 | 716 | 20.44% | 6.81% | 46.80 |
| Original IF 43 | 10% | 1800 | 394 | 1406 | 21.89% | 14.59% | 91.90 |
| Original IF 44 | 1% | 180 | 50 | 130 | 27.78% | 1.85% | 8.50 |
| Original IF 44 | 2% | 360 | 77 | 283 | 21.39% | 2.85% | 18.50 |
| Original IF 44 | 5% | 900 | 200 | 700 | 22.22% | 7.41% | 45.75 |
| Original IF 44 | 10% | 1800 | 411 | 1389 | 22.83% | 15.22% | 90.78 |
| Tuned IF 42 | 1% | 180 | 54 | 126 | 30.00% | 2.00% | 8.24 |
| Tuned IF 42 | 2% | 360 | 95 | 265 | 26.39% | 3.52% | 17.32 |
| Tuned IF 42 | 5% | 900 | 203 | 697 | 22.56% | 7.52% | 45.56 |
| Tuned IF 42 | 10% | 1800 | 433 | 1367 | 24.06% | 16.04% | 89.35 |
| Tuned IF 43 | 1% | 180 | 53 | 127 | 29.44% | 1.96% | 8.30 |
| Tuned IF 43 | 2% | 360 | 97 | 263 | 26.94% | 3.59% | 17.19 |
| Tuned IF 43 | 5% | 900 | 190 | 710 | 21.11% | 7.04% | 46.41 |
| Tuned IF 43 | 10% | 1800 | 411 | 1389 | 22.83% | 15.22% | 90.78 |
| Tuned IF 44 | 1% | 180 | 56 | 124 | 31.11% | 2.07% | 8.10 |
| Tuned IF 44 | 2% | 360 | 98 | 262 | 27.22% | 3.63% | 17.12 |
| Tuned IF 44 | 5% | 900 | 211 | 689 | 23.44% | 7.81% | 45.03 |
| Tuned IF 44 | 10% | 1800 | 414 | 1386 | 23.00% | 15.33% | 90.59 |
| Heuristic | 1% | 180 | 53 | 127 | 29.44% | 1.96% | 8.30 |
| Heuristic | 2% | 360 | 78 | 282 | 21.67% | 2.89% | 18.43 |
| Heuristic | 5% | 900 | 172 | 728 | 19.11% | 6.37% | 47.58 |
| Heuristic | 10% | 1800 | 470 | 1330 | 26.11% | 17.41% | 86.93 |

At top 1%, original IF mean precision is **27.59% +/- 0.26 percentage points**, versus tuned **30.19% +/- 0.69 points**. Corresponding mean recall is **1.84% versus 2.01%**; mean true alerts **49.67 versus 54.33**, and false alerts **130.33 versus 125.67**. The heuristic produces 53 true / 127 false alerts (29.44% precision, 1.96% recall).

## Fixed validation-budget thresholds on final data

Numerical cutoffs were frozen from validation, include every score tie with >=, and do not guarantee the same alert fraction on a different population. Representative seed-42 comparisons below; all seven models and confusion matrices are in JSON.

| Model | Validation cutoff target | Final alerts | True | False | Precision | Recall | FPR |
|---|---:|---:|---:|---:|---:|---:|---:|
| Original IF 42 | 1% | 182 | 50 | 132 | 27.47% | 1.85% | 0.86% |
| Original IF 42 | 2% | 341 | 85 | 256 | 24.93% | 3.15% | 1.67% |
| Original IF 42 | 5% | 866 | 185 | 681 | 21.36% | 6.85% | 4.45% |
| Original IF 42 | 10% | 1742 | 382 | 1360 | 21.93% | 14.15% | 8.89% |
| Tuned IF 42 | 1% | 180 | 54 | 126 | 30.00% | 2.00% | 0.82% |
| Tuned IF 42 | 2% | 336 | 91 | 245 | 27.08% | 3.37% | 1.60% |
| Tuned IF 42 | 5% | 834 | 196 | 638 | 23.50% | 7.26% | 4.17% |
| Tuned IF 42 | 10% | 1794 | 431 | 1363 | 24.02% | 15.96% | 8.91% |
| Heuristic | 1% | 178 | 52 | 126 | 29.21% | 1.93% | 0.82% |
| Heuristic | 2% | 371 | 80 | 291 | 21.56% | 2.96% | 1.90% |
| Heuristic | 5% | 925 | 183 | 742 | 19.78% | 6.78% | 4.85% |
| Heuristic | 10% | 1790 | 469 | 1321 | 26.20% | 17.37% | 8.63% |

## Category recall at frozen F1 thresholds

| Category | Transactions / scenarios | Original 42 | Original 43 | Original 44 | Tuned 42 | Tuned 43 | Tuned 44 | Heuristic |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| dust_attack | 405 / 5 | 100.00% | 97.53% | 99.26% | 100.00% | 96.05% | 99.75% | 100.00% |
| fee_anomaly | 270 / 270 | 91.11% | 88.52% | 90.74% | 88.89% | 89.63% | 91.11% | 100.00% |
| high_value_single_hop | 405 / 405 | 86.42% | 83.21% | 87.90% | 85.19% | 84.94% | 90.37% | 100.00% |
| anomalous_port_usage | 405 / 405 | 39.01% | 35.56% | 35.80% | 29.63% | 32.10% | 34.81% | 41.98% |
| geo_velocity_impossible_travel | 270 / 135 | 41.85% | 39.63% | 39.26% | 31.11% | 33.70% | 37.41% | 40.37% |
| peeling_chain | 405 / 17 | 26.91% | 18.27% | 23.70% | 19.75% | 23.46% | 23.70% | 86.67% |
| rapid_fire_layering | 540 / 18 | 24.63% | 18.33% | 18.33% | 11.11% | 12.78% | 24.63% | 33.15% |

## Does the validation improvement generalize?

**Modestly for the selected primary objective on this synthetic population.** Mean top-1% precision improves by 2.59 percentage points, or 4.67 additional true alerts per 180 reviews. Mean F1 improves from 0.2871 to 0.2967; mean AP from 0.1963 to 0.2058; mean ROC-AUC from 0.5911 to 0.6069. Mean FPR falls from 39.00% to 34.63%, but mean recall also falls from 53.80% to 51.62%.

This is a tradeoff, not uniformly better detection. Tuned seed 42 has rapid-layering recall **11.11% versus 24.63%** for original seed 42, and peeling **19.75% versus 26.91%**. The heuristic remains stronger at F1 (0.3347) and recall (69.96%), although its FPR is 43.78%. Top-1% tuned alerts are still about 70% false positives, and recall is only about 2%. No result prompted a model, threshold, seed or policy change.

Validation-only false-positive analysis found strong concentration in tiny amounts and high fees; historical activity intensity did not show a simple high-activity explanation. See [the false-positive report](ml_false_positive_analysis.md). Those are hypotheses about correlations, not causal feature attribution; no final-test false-positive exploration or record removal was performed.

Fresh identities do not create new scenario mechanisms: all populations share the unchanged generator, fee/amount construction and timing rules. Calendar features can shift across windows. Dust has only five scenarios. Port/geo mechanisms are not represented directly in the numerical features. Scores are not probabilities, ownership evidence, criminality labels or real-world deployment accuracy.

## Executed validation and reproduction

- Production tuning: exactly 36 fits, 171.49s. No production tuning/refitting was repeated for seed 405.
- Final generation: 5.82s; all seven model scoring calls total 3.37s; one final workflow including generation, ingestion, audits and evaluation: 20.63s.
- Amendment-focused tests: 17 passed in 6.34s, no warnings.
- Complete final regression suite: **199 passed + 75 passing subtests**, zero failures/skips, one known Starlette/httpx TestClient deprecation warning, **195.75s**. An interrupted earlier session had no recoverable final result; this measured rerun is the reported result.
- Earlier tuning checks are preserved in `checks.json`: 182 tests + 75 subtests in 128.82s after fixture correction, plus focused phase history.
- `pip check`: no broken requirements. Git diff and ignored-artifact checks passed. All 58 protected original files and 130 original tuning-frozen files retain their hashes.
- Timings are observations on this environment, not benchmarks. No dependency changes were needed.

From the repository root, using existing frozen artifacts (each command refuses existing outputs):

```powershell
Push-Location backend
..\venv\Scripts\python.exe -B -m app.ml.final_evaluation inventory --config ../configs/ml_final_405.json
..\venv\Scripts\python.exe -B -m app.ml.final_evaluation reserve --config ../configs/ml_final_405.json
..\venv\Scripts\python.exe -B -m app.ml.final_evaluation evaluate --config ../configs/ml_final_405.json
..\venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider
Pop-Location
.\venv\Scripts\python.exe -B -m pip check
```

The commands above describe the completed one-shot run; do not rerun evaluation against its existing outputs. For exact reproduction into unused paths, see [the protocol](ml_tuning.md). Compact reports: `reports/ml/tuning/run-001/{search,selection,validation,false_positives,fixture_manifest,seed_change,final_manifest,final_evaluation,final_checks}.json`. Large corpora, models, identity inventories and score files are ignored.

Graph-based wallet/transaction relationships and causal temporal features remain the next separate milestone. Preserve this frozen experiment; do not tune graph methods on the now-published seed-405 results. No commit, push or merge has been performed.
