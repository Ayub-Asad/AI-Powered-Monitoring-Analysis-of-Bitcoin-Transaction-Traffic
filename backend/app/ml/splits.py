"""Label-free partition auditing using transaction and grouping sidecars."""
from itertools import combinations
import pandas as pd


def audit_partitions(partitions):
    identities, summary = {}, {}
    for name in ("train", "validation", "test"):
        tx, groups = partitions[name]
        if {"label", "anomaly_type"} & (set(tx.columns) | set(groups.columns)):
            raise ValueError("partition audit must not receive labels")
        if len(tx) == 0 or tx.txid.duplicated().any() or groups.txid.duplicated().any():
            raise ValueError("empty partition or duplicate IDs")
        if set(tx.txid) != set(groups.txid):
            raise ValueError("group metadata coverage mismatch")
        if not groups.corpus.eq(name).all() or groups.isna().any().any():
            raise ValueError("invalid corpus scope")
        for column in ("actor_id", "scenario_id"):
            if not groups[column].str.startswith(name + ":").all():
                raise ValueError("unscoped identity")
        if (groups.groupby("scenario_id").actor_id.nunique() != 1).any():
            raise ValueError("scenario has multiple generating actors")
        times = pd.to_datetime(tx.timestamp, utc=True)
        identities[name] = {"txid": set(tx.txid), "wallet": {a for col in ("input_addresses", "output_addresses") for row in tx[col] for a in row},
                            "actor": set(groups.actor_id), "scenario": set(groups.scenario_id),
                            "raw_scenario": {s.split(":", 1)[1] for s in groups.scenario_id}}
        summary[name] = {"records": len(tx), "start": times.min().isoformat(), "end": times.max().isoformat(),
                         **{k + "_count": len(v) for k, v in identities[name].items()}}
    overlaps = {}
    for a, b in combinations(("train", "validation", "test"), 2):
        overlaps[a + "_" + b] = {k: len(identities[a][k] & identities[b][k]) for k in identities[a]}
        if any(overlaps[a + "_" + b].values()):
            raise ValueError(f"partition identity overlap: {a}/{b}")
        if pd.Timestamp(summary[a]["end"]) >= pd.Timestamp(summary[b]["start"]):
            raise ValueError("observation periods overlap or are out of order")
    return {"partitions": summary, "overlaps": overlaps, "chronological": True}
