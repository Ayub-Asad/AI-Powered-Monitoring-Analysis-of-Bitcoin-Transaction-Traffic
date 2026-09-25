"""Generate and audit reproducible artifacts; evaluation labels stay outside features."""
import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))
import numpy as np
import pandas as pd
from app.ingestion import ingest_file
from app.money import to_satoshis
from scripts.dataset_v2 import BitcoinDatasetV2Generator
from scripts.btc_synthetic_dataset_generator import write_csv, write_jsonl


def quality_report(transactions, ground_truth):
    # Evaluation-only join. This frame is never passed to feature engineering.
    frame = transactions.merge(ground_truth, on="txid", validate="one_to_one")
    y = (frame.label == "anomalous").to_numpy()
    frame["hour_utc"] = frame.timestamp.dt.hour
    frame["day_utc"] = frame.timestamp.dt.dayofweek
    frame["date_utc"] = frame.timestamp.dt.strftime("%Y-%m-%d")
    frame["src_port_class"] = frame.src_port.map(lambda p: str(p) if p < 1024 or p in [9050, 4444, 31337, 6667, 1337] else "ephemeral")
    numeric = {}
    for name in ["amount_btc", "fee_btc", "fee_rate_sat_vb", "num_inputs", "num_outputs", "hour_utc", "day_utc"]:
        x = frame[name].to_numpy(dtype=float)
        order = np.argsort(x, kind="stable")
        xs, ys = x[order], y[order]
        boundaries = np.r_[np.flatnonzero(xs[:-1] != xs[1:]), len(xs)-1]
        positives, negatives = ys.cumsum()[boundaries], (~ys).cumsum()[boundaries]
        low = (positives/y.sum() + 1-negatives/(~y).sum()) / 2
        high = 1-low
        score = float(max(low.max(), high.max(), 0.5))
        numeric[name] = {label: {str(q): float(frame.loc[frame.label == label, name].quantile(q))
                                for q in [0, .01, .1, .5, .9, .99, 1]} for label in ["normal", "anomalous"]}
        numeric[name]["best_single_threshold_balanced_accuracy_descriptive_only"] = score
    contextual = {}
    shortcuts = []
    for name in ["country", "asn", "dst_port", "src_port_class", "hour_utc", "date_utc"]:
        tab = pd.crosstab(frame[name], frame.label).reindex(columns=["normal", "anomalous"], fill_value=0)
        contextual[name] = {str(k): {col: int(v) for col, v in row.items()} for k, row in tab.iterrows()}
        for k, row in tab.iterrows():
            if row["normal"] == 0 and row["anomalous"] >= 5:
                shortcuts.append({"field": name, "value": str(k), "anomalous_only_support": int(row["anomalous"])})
    return {"numerical_by_label": numeric, "contextual_by_label": contextual,
            "anomalous_only_context_values_support_at_least_5": shortcuts,
            "interpretation": "Descriptive synthetic-data diagnostics, not held-out model performance. Overlap does not establish realism or eliminate multivariate shortcuts.",
            "limitations": ["Injected chain and dust structures remain deliberately distinctive.",
                            "Rapid layering can remain distinctive through fee/value combinations.",
                            "Port and geo scenarios rely on investigative context excluded from default ML features.",
                            "No real GeoIP, wallet ownership, full UTXO history or real-world traffic calibration."]}


def generate_dataset(name, normal, anomalous, seed, output):
    started = time.perf_counter()
    generator = BitcoinDatasetV2Generator(seed)
    rows = generator.generate(normal, anomalous)
    generation_seconds = time.perf_counter() - started
    csv_path, jsonl_path = output / (name + ".csv"), output / (name + ".jsonl")
    write_csv(rows, csv_path)
    write_jsonl(rows, jsonl_path)
    generator.write_metadata(rows, csv_path, [csv_path, jsonl_path])
    return rows, csv_path, jsonl_path, generation_seconds


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out-dir", type=Path, default=ROOT / "data/v2")
    parser.add_argument("--dataset-only", action="store_true")
    args = parser.parse_args()
    output = args.out_dir
    output.mkdir(parents=True, exist_ok=True)
    rows, csv_path, jsonl_path, generation_seconds = generate_dataset("development", 15300, 2700, args.seed, output)
    generate_dataset("regression", 850, 150, args.seed, output)
    second = BitcoinDatasetV2Generator(args.seed).generate(15300, 2700)
    assert rows == second, "seed determinism failed"
    t = time.perf_counter()
    result = ingest_file(csv_path)
    ingestion_seconds = time.perf_counter()-t
    other = ingest_file(jsonl_path)
    pd.testing.assert_frame_equal(result.transactions, other.transactions)
    pd.testing.assert_frame_equal(result.ground_truth, other.ground_truth)
    frame = result.transactions
    failures = sum(sum(map(to_satoshis, r.input_amounts)) != sum(map(to_satoshis, r.output_amounts)) + to_satoshis(r.fee_btc)
                   or sum(map(to_satoshis, r.output_amounts)) != to_satoshis(r.amount_btc) for r in rows)
    assert failures == 0
    assert result.report.valid_rows == 18000 and result.report.rejected_rows == result.report.duplicate_rows == 0
    assert not {"label", "anomaly_type", "ground_truth", "actor_id", "scenario_id"} & set(frame)
    report = {"seed": args.seed, "records": len(frame), "labels": dict(Counter(r.label for r in rows)),
              "anomaly_distribution": dict(Counter(r.anomaly_type for r in rows if r.anomaly_type)),
              "unique_wallets": len({a for name in ["input_addresses", "output_addresses"] for addresses in frame[name] for a in addresses}),
              "unique_ips": len(set(frame.src_ip) | set(frame.dst_ip)), "canonical_shape": list(frame.shape),
              "canonical_missing": frame.isna().sum().to_dict(),
              "canonical_infinite": int(np.isinf(frame.select_dtypes(include="number").to_numpy(dtype=float)).sum()),
              "duplicate_txids": int(frame.txid.duplicated().sum()), "monetary_conservation_failures": failures,
              "generation_seconds": generation_seconds, "csv_ingestion_seconds": ingestion_seconds,
              "csv_jsonl_equivalent": True, "seed_deterministic": True,
              "ingestion_warnings": dict(result.report.warning_counts),
              "legacy_sha256": hashlib.sha256((ROOT / "data/btc_synthetic_dataset.csv").read_bytes()).hexdigest()}
    quality = quality_report(frame, result.ground_truth)
    (output / "quality_report.json").write_text(json.dumps(quality, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    if not args.dataset_only:
        from app.features import extract_features
        from app.features.schema import TRANSACTION_ML_FEATURES, WALLET_ML_FEATURES
        t = time.perf_counter()
        features = extract_features(frame)
        report["feature_seconds"] = time.perf_counter()-t
        for name, table, selected in [("transaction", features.transaction_features, TRANSACTION_ML_FEATURES),
                                      ("wallet", features.wallet_features, WALLET_ML_FEATURES)]:
            table.to_csv(output / (name+"_features.csv"), index=False)
            values = table[list(selected)].to_numpy(dtype=float)
            report[name+"_features"] = {"shape": list(table.shape), "selected_ml_columns": len(selected),
                                       "missing": table.isna().sum().to_dict(),
                                       "selected_infinite": int(np.isinf(values).sum()),
                                       "selected_nan": int(np.isnan(values).sum())}
            assert np.isfinite(values).all()
        features.wallet_context.to_csv(output / "wallet_context.csv", index=False)
        features.transaction_context.to_csv(output / "transaction_context.csv", index=False)
        from app.features import schema as feature_schema
        feature_manifest = {"burst_window_seconds": features.config.burst_window_seconds,
                            "transaction_ml_features": feature_schema.TRANSACTION_ML_FEATURES,
                            "wallet_ml_features": feature_schema.WALLET_ML_FEATURES,
                            "wallet_extra_behavioural_features": feature_schema.WALLET_EXTRA_BEHAVIOURAL_FEATURES,
                            "wallet_availability_fields": feature_schema.WALLET_AVAILABILITY_FIELDS,
                            "transaction_context_fields": feature_schema.TRANSACTION_CONTEXT_FIELDS,
                            "wallet_context_features": feature_schema.WALLET_CONTEXT_FEATURES,
                            "identifiers": feature_schema.IDENTIFIERS,
                            "unavailable_for_legacy": feature_schema.UNAVAILABLE_FOR_LEGACY,
                            "estimated_features": feature_schema.ESTIMATED_FEATURES}
        (output / "feature_manifest.json").write_text(json.dumps(feature_manifest, indent=2)+"\n", encoding="utf-8")
        report["transaction_context_shape"] = list(features.transaction_context.shape)
        report["wallet_context_shape"] = list(features.wallet_context.shape)
        again = extract_features(frame.sample(frac=1, random_state=13))
        pd.testing.assert_frame_equal(features.transaction_features, again.transaction_features)
        pd.testing.assert_frame_equal(features.wallet_features, again.wallet_features)
        report["feature_order_independent"] = True
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as client:
        health = client.get("/health")
        api = client.post("/ingest", files={"file": (csv_path.name, csv_path.read_bytes(), "text/csv")})
        api_jsonl = client.post("/ingest", files={"file": (jsonl_path.name, jsonl_path.read_bytes(), "application/x-ndjson")})
    assert health.status_code == api.status_code == api_jsonl.status_code == 200
    assert api.json()["summary"]["valid_rows"] == api_jsonl.json()["summary"]["valid_rows"] == 18000
    report["api"] = {"method": "FastAPI TestClient (in-process ASGI)", "health": health.status_code,
                     "csv": api.status_code, "jsonl": api_jsonl.status_code, "valid_rows": 18000}
    (output / "validation_report.json").write_text(json.dumps(report, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    print("Anomalous-only contextual values with support >= 5:", quality["anomalous_only_context_values_support_at_least_5"])
    print("Single-threshold descriptive balanced accuracies:", {k: round(v["best_single_threshold_balanced_accuracy_descriptive_only"], 3) for k,v in quality["numerical_by_label"].items()})


if __name__ == "__main__":
    main()
