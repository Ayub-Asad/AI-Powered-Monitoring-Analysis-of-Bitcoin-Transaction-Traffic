"""Regenerate independent corpora. Transaction files contain no evaluation labels."""
import argparse
from dataclasses import asdict
from datetime import datetime
import json
from pathlib import Path
import sys
import time
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))
from scripts.dataset_v2 import BitcoinDatasetV2Generator
from app.ml.schema import load_config, write_json, digest, validate_config
from app.ml.splits import audit_partitions


def write_lines(path, rows):
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, sort_keys=True, allow_nan=False) + "\n")


def prepare(config, root=ROOT):
    validate_config(config)
    output = root / config["data_dir"]
    output.mkdir(parents=True, exist_ok=True)
    partitions, manifests = {}, {}
    for name in ("train", "validation", "test"):
        spec = config["corpora"][name]
        started = time.perf_counter()
        generator = BitcoinDatasetV2Generator(spec["seed"], datetime.fromisoformat(spec["start_time"]))
        rows = generator.generate(spec["normal"], spec["anomalous"])
        records = [{k: v for k, v in asdict(row).items() if k not in {"label", "anomaly_type"}} for row in rows]
        groups = [{"txid": row["txid"], "corpus": name, "actor_id": name + ":" + row["actor_id"],
                   "scenario_id": name + ":" + row["scenario_id"]} for row in generator.ground_truth]
        # Generation serializes truth; neither split auditing nor training reads it.
        truth = [{k: row[k] for k in ("txid", "label", "anomaly_type")} for row in generator.ground_truth]
        for suffix, data in (("transactions", records), ("groups", groups), ("labels", truth)):
            write_lines(output / f"{name}.{suffix}.jsonl", data)
        partitions[name] = pd.DataFrame(records), pd.DataFrame(groups)
        manifests[name] = {"generation": spec, "records": len(records), "complete_scenarios": True,
                           "generation_seconds": time.perf_counter() - started,
                           "files": {f"{name}.{suffix}.jsonl": digest(output / f"{name}.{suffix}.jsonl") for suffix in ("transactions", "groups", "labels")}}
    audit = audit_partitions(partitions)
    report = {"experiment_version": config["experiment_version"], "corpora": manifests, "split_audit": audit}
    write_json(output / "manifest.json", report)
    write_json(root / config["report_dir"] / "corpus_manifest.json", report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/ml_baseline.json")
    args = parser.parse_args()
    print(json.dumps(prepare(load_config(args.config)), indent=2))
