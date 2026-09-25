"""Export feature tables from CSV/JSON/JSONL through canonical ingestion."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
from ..ingestion import ingest_file
from . import extract_features, FeatureConfig
from .schema import (TRANSACTION_ML_FEATURES, WALLET_ML_FEATURES, WALLET_CONTEXT_FEATURES,
                     TRANSACTION_CONTEXT_FIELDS, IDENTIFIERS, UNAVAILABLE_FOR_LEGACY, ESTIMATED_FEATURES,
                     WALLET_EXTRA_BEHAVIOURAL_FEATURES, WALLET_AVAILABILITY_FIELDS)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path")
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--burst-window-seconds", type=float, default=60)
    args = parser.parse_args()
    result = ingest_file(args.path)
    if result.report.status == "failed":
        print(json.dumps(result.report.to_dict(), indent=2))
        return 1
    features = extract_features(result.transactions, FeatureConfig(args.burst_window_seconds))
    args.out_dir.mkdir(parents=True, exist_ok=True)
    for name in ["transaction_features", "wallet_features", "transaction_context", "wallet_context"]:
        getattr(features, name).to_csv(args.out_dir / (name+".csv"), index=False)
    manifest = {"config": asdict(features.config), "identifiers": IDENTIFIERS,
                "transaction_ml_features": TRANSACTION_ML_FEATURES, "wallet_ml_features": WALLET_ML_FEATURES,
                "wallet_extra_behavioural_features": WALLET_EXTRA_BEHAVIOURAL_FEATURES,
                "wallet_availability_fields": WALLET_AVAILABILITY_FIELDS,
                "transaction_context_fields": TRANSACTION_CONTEXT_FIELDS, "wallet_context_features": WALLET_CONTEXT_FEATURES,
                "unavailable_for_legacy": UNAVAILABLE_FOR_LEGACY, "estimated_features": ESTIMATED_FEATURES,
                "ingestion_report": result.report.to_dict()}
    (args.out_dir / "feature_manifest.json").write_text(json.dumps(manifest, indent=2)+"\n", encoding="utf-8")
    print(f"Exported {len(features.transaction_features)} transactions and {len(features.wallet_features)} wallets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
