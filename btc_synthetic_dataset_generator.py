"""
Synthetic Bitcoin Transaction Dataset Generator
================================================
Problem Statement: PS 26146

Generates a reproducible, labelled synthetic dataset of Bitcoin-like network
transactions, combining normal (benign) behavioural patterns with several
classes of anomalous / suspicious behaviour. Intended for use in training
and evaluating anomaly-detection / fraud-detection models.

Fields produced per record:
    timestamp        - ISO-8601 UTC timestamp of the transaction
    src_ip            - source IP address (peer originating the tx)
    dst_ip            - destination IP address (peer receiving/relaying)
    src_port          - source TCP port
    dst_port          - destination TCP port
    txid              - synthetic 64-hex-char transaction id
    input_addresses   - pipe-separated list of input wallet addresses
    output_addresses  - pipe-separated list of output wallet addresses
    num_inputs        - number of inputs
    num_outputs       - number of outputs
    amount_btc        - total transacted amount (BTC)
    fee_btc           - miner fee (BTC)
    fee_rate_sat_vb   - approximate fee rate (sat/vByte)
    country           - ISO country code associated with src_ip
    asn               - Autonomous System Number associated with src_ip
    asn_org           - human-readable ASN organisation name
    label             - "normal" or "anomalous"
    anomaly_type      - specific anomaly category (empty for normal rows)

Usage:
    python btc_synthetic_dataset_generator.py --n-normal 8000 --n-anomalous 800 \
        --seed 42 --out dataset.csv

Design notes:
    - Everything is driven by a single `random.Random` / `numpy` seed so the
      output is byte-for-byte reproducible across runs.
    - Addresses, txids and IPs are synthetic look-alikes (correct format,
      correct length/charset) — NOT real chain data and NOT drawn from any
      real address list.
    - Anomaly generators are self-contained functions so new anomaly classes
      can be added without touching the normal-traffic logic.
"""

import argparse
import csv
import hashlib
import ipaddress
import json
import random
import string
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from typing import List, Tuple


# --------------------------------------------------------------------------
# Reference data: synthetic country / ASN pools
# --------------------------------------------------------------------------

# A small pool of (country_iso2, [ (asn, asn_org), ... ]) used to assign
# geo/network context to generated IPs in a self-consistent way.
COUNTRY_ASN_POOL = {
    "US": [(15169, "GOOGLE"), (16509, "AMAZON-02"), (7922, "COMCAST-7922"), (701, "UUNET")],
    "DE": [(3320, "DTAG"), (8560, "IONOS-AS"), (24940, "HETZNER-AS")],
    "NL": [(14061, "DIGITALOCEAN-ASN"), (60781, "LEASEWEB-NL"), (16276, "OVH")],
    "SG": [(45102, "ALIBABA-CN-NET"), (55960, "HWCSNET"), (132203, "TENCENT-NET-AP")],
    "RU": [(12389, "ROSTELECOM-AS"), (49505, "OBIT-AS"), (8402, "CORBINA-AS")],
    "IN": [(55836, "RELIANCEJIO-IN"), (45609, "BHARTI-AIRTEL"), (9829, "BSNL-NIB")],
    "GB": [(2856, "BT-UK-AS"), (5089, "VIRGINMEDIA"), (20712, "GB-KUEHNENAGEL")],
    "BR": [(28573, "CLARO-BR"), (26599, "TELEFONICA-BR"), (8167, "PONTONET-BR")],
    "CN": [(4134, "CHINANET-BACKBONE"), (4837, "CHINA169-BACKBONE"), (9808, "CMNET-GD")],
    "IR": [(12880, "IRANCELL-AS"), (58224, "TIC-AS"), (44244, "IRANCELL-PLC")],  # historically OFAC-flagged region
    "KP": [(131279, "STAR-KP")],  # sparsely-routed / sanctioned region
    "NG": [(37148, "MAINONE-AS"), (36873, "GLOBALCOM-AS")],
    "AE": [(5384, "EMIRATES-INTERNET"), (15802, "DU-AS")],
    "PA": [(52468, "PANAMA-DC")],  # common offshore-mixer jurisdiction proxy
}

NORMAL_COUNTRIES = ["US", "DE", "NL", "SG", "IN", "GB", "BR"]
HIGH_RISK_COUNTRIES = ["RU", "IR", "KP", "NG", "PA"]  # over-represented in anomalous traffic

BITCOIN_PORTS_NORMAL = [8333, 18333]          # mainnet / testnet P2P
BITCOIN_PORTS_RPC = [8332, 18332]              # RPC (rarely peer-to-peer)
UNUSUAL_PORTS = [443, 9050, 4444, 31337, 6667, 1337, 22]  # tor/proxy/backdoor-like


# --------------------------------------------------------------------------
# Data model
# --------------------------------------------------------------------------

@dataclass
class Transaction:
    timestamp: str
    src_ip: str
    dst_ip: str
    src_port: int
    dst_port: int
    txid: str
    input_addresses: str
    output_addresses: str
    num_inputs: int
    num_outputs: int
    amount_btc: float
    fee_btc: float
    fee_rate_sat_vb: float
    country: str
    asn: int
    asn_org: str
    label: str
    anomaly_type: str


# --------------------------------------------------------------------------
# Generator
# --------------------------------------------------------------------------

class BitcoinDatasetGenerator:
    def __init__(self, seed: int = 42, start_time: datetime = None):
        self.seed = seed
        self.rng = random.Random(seed)
        self.start_time = start_time or datetime(2025, 1, 1, tzinfo=timezone.utc)
        # a reusable pool of "wallet identities" so the same address can
        # legitimately reappear across transactions (as in real chains)
        self._address_pool: List[str] = [self._make_address() for _ in range(4000)]
        # small pool of "actor" IPs so behavioural bursts share a source
        self._actor_ip_cache = {}

    # ---- low-level synthetic primitives ---------------------------------

    def _hex(self, n_bytes: int) -> str:
        return "".join(self.rng.choice("0123456789abcdef") for _ in range(n_bytes * 2))

    def _make_txid(self) -> str:
        return self._hex(32)

    def _make_address(self) -> str:
        """Synthetic bech32-like / base58-like address (format-correct,
        not a real chain address)."""
        style = self.rng.choice(["bech32", "base58"])
        if style == "bech32":
            charset = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
            body = "".join(self.rng.choice(charset) for _ in range(38))
            return "bc1q" + body
        else:
            charset = string.ascii_letters + string.digits
            charset = "".join(c for c in charset if c not in "0OIl")
            body = "".join(self.rng.choice(charset) for _ in range(33))
            return "1" + body

    def _random_public_ip(self, country: str) -> str:
        """Deterministic-looking but random public IPv4 for a given country
        bucket (not a real geo-IP lookup — synthetic association only)."""
        while True:
            ip = ipaddress.IPv4Address(self.rng.randint(1, 2**32 - 1))
            if ip.is_global and not ip.is_multicast:
                return str(ip)

    def _pick_country_asn(self, high_risk_bias: float = 0.0) -> Tuple[str, int, str]:
        if self.rng.random() < high_risk_bias:
            country = self.rng.choice(HIGH_RISK_COUNTRIES)
        else:
            country = self.rng.choice(NORMAL_COUNTRIES)
        asn, org = self.rng.choice(COUNTRY_ASN_POOL[country])
        return country, asn, org

    def _sample_addresses(self, k: int) -> List[str]:
        # occasionally mint a brand-new address (fresh wallet), otherwise
        # reuse one from the pool (realistic reuse behaviour)
        out = []
        for _ in range(k):
            if self.rng.random() < 0.05:
                addr = self._make_address()
                self._address_pool.append(addr)
            else:
                addr = self.rng.choice(self._address_pool)
            out.append(addr)
        return out

    def _timestamp_at(self, offset_seconds: float) -> str:
        ts = self.start_time + timedelta(seconds=offset_seconds)
        return ts.strftime("%Y-%m-%dT%H:%M:%SZ")

    # ---- normal traffic ---------------------------------------------------

    def generate_normal(self, n: int) -> List[Transaction]:
        """Normal wallet-to-wallet traffic:
        - inter-arrival times ~ exponential (Poisson process), few tx/min
        - amounts ~ log-normal, small fee proportional to size
        - standard P2P ports, geo drawn from common countries
        - 1-3 inputs, 1-2 outputs (typical spend + change)
        """
        records = []
        t = 0.0
        for _ in range(n):
            t += self.rng.expovariate(1 / 45.0)  # avg ~45s between tx
            country, asn, org = self._pick_country_asn(high_risk_bias=0.03)
            src_ip = self._random_public_ip(country)
            dst_country, dst_asn, dst_org = self._pick_country_asn(high_risk_bias=0.03)
            dst_ip = self._random_public_ip(dst_country)

            n_in = self.rng.choice([1, 1, 1, 2, 3])
            n_out = self.rng.choice([1, 1, 2, 2])
            inputs = self._sample_addresses(n_in)
            outputs = self._sample_addresses(n_out)

            amount = round(max(0.0001, self.rng.lognormvariate(-2.5, 1.2)), 8)
            fee_rate = round(self.rng.uniform(8, 40), 2)          # sat/vByte, typical
            vbytes = 140 + 40 * n_in + 30 * n_out
            fee_btc = round((fee_rate * vbytes) / 1e8, 8)

            rec = Transaction(
                timestamp=self._timestamp_at(t),
                src_ip=src_ip,
                dst_ip=dst_ip,
                src_port=self.rng.randint(1024, 65535),
                dst_port=self.rng.choice(BITCOIN_PORTS_NORMAL),
                txid=self._make_txid(),
                input_addresses="|".join(inputs),
                output_addresses="|".join(outputs),
                num_inputs=n_in,
                num_outputs=n_out,
                amount_btc=amount,
                fee_btc=fee_btc,
                fee_rate_sat_vb=fee_rate,
                country=country,
                asn=asn,
                asn_org=org,
                label="normal",
                anomaly_type="",
            )
            records.append(rec)
        return records

    # ---- anomaly generators -------------------------------------------------
    # Each returns a list[Transaction] tagged with label="anomalous" and a
    # specific anomaly_type. Anomaly classes modelled:
    #   1. rapid_fire_layering   - many tiny tx in a very short burst from
    #                              one actor (layering / mixing behaviour)
    #   2. dust_attack           - large fan-out of dust-sized outputs to
    #                              many addresses (address de-anonymisation)
    #   3. high_value_single_hop - unusually large single transaction moved
    #                              in one hop straight to a high-risk geo
    #   4. peeling_chain         - long chain of near-identical "peel off a
    #                              little, forward the rest" transactions
    #   5. anomalous_port_scan   - traffic on non-standard / proxy-like ports
    #   6. fee_anomaly           - abnormally high or abnormally (near-zero)
    #                              fee relative to tx size
    #   7. geo_velocity          - same address pair seen from geographically
    #                              impossible sequential locations in a short
    #                              time window ("impossible travel")

    def _burst_actor_ip(self, key: str, country: str) -> str:
        if key not in self._actor_ip_cache:
            self._actor_ip_cache[key] = self._random_public_ip(country)
        return self._actor_ip_cache[key]

    def gen_rapid_fire_layering(self, n_clusters: int, base_t: float) -> List[Transaction]:
        records = []
        for c in range(n_clusters):
            t = base_t + self.rng.uniform(0, 5000)
            country, asn, org = self._pick_country_asn(high_risk_bias=0.6)
            src_ip = self._burst_actor_ip(f"layer_{c}", country)
            burst_len = self.rng.randint(15, 60)
            hop_addr = self._make_address()
            for i in range(burst_len):
                t += self.rng.uniform(0.5, 3.0)  # sub-second-to-few-second spacing
                dst_country, dst_asn, dst_org = self._pick_country_asn(high_risk_bias=0.6)
                dst_ip = self._random_public_ip(dst_country)
                next_hop = self._make_address()
                amount = round(self.rng.uniform(0.0005, 0.01), 8)
                fee_btc = round(amount * self.rng.uniform(0.0005, 0.002), 8)
                records.append(Transaction(
                    timestamp=self._timestamp_at(t),
                    src_ip=src_ip, dst_ip=dst_ip,
                    src_port=self.rng.randint(1024, 65535),
                    dst_port=self.rng.choice(BITCOIN_PORTS_NORMAL + UNUSUAL_PORTS),
                    txid=self._make_txid(),
                    input_addresses=hop_addr,
                    output_addresses=next_hop,
                    num_inputs=1, num_outputs=1,
                    amount_btc=amount, fee_btc=fee_btc,
                    fee_rate_sat_vb=round(self.rng.uniform(1, 5), 2),
                    country=country, asn=asn, asn_org=org,
                    label="anomalous", anomaly_type="rapid_fire_layering",
                ))
                hop_addr = next_hop
        return records

    def gen_dust_attack(self, n_clusters: int, base_t: float) -> List[Transaction]:
        records = []
        for c in range(n_clusters):
            t = base_t + self.rng.uniform(0, 5000)
            country, asn, org = self._pick_country_asn(high_risk_bias=0.4)
            src_ip = self._burst_actor_ip(f"dust_{c}", country)
            n_out = self.rng.randint(50, 300)
            outputs = [self._make_address() for _ in range(n_out)]
            for out_addr in outputs:
                t += self.rng.uniform(0.01, 0.2)
                dust = round(self.rng.uniform(0.00000546, 0.00003), 8)  # near dust limit
                records.append(Transaction(
                    timestamp=self._timestamp_at(t),
                    src_ip=src_ip, dst_ip=self._random_public_ip(country),
                    src_port=self.rng.randint(1024, 65535),
                    dst_port=self.rng.choice(BITCOIN_PORTS_NORMAL),
                    txid=self._make_txid(),
                    input_addresses=self.rng.choice(self._address_pool),
                    output_addresses=out_addr,
                    num_inputs=1, num_outputs=1,
                    amount_btc=dust,
                    fee_btc=round(dust * 0.3, 8),
                    fee_rate_sat_vb=round(self.rng.uniform(1, 10), 2),
                    country=country, asn=asn, asn_org=org,
                    label="anomalous", anomaly_type="dust_attack",
                ))
        return records

    def gen_high_value_single_hop(self, n: int, base_t: float) -> List[Transaction]:
        records = []
        for _ in range(n):
            t = base_t + self.rng.uniform(0, 20000)
            country, asn, org = self._pick_country_asn(high_risk_bias=0.85)
            src_country, s_asn, s_org = self._pick_country_asn(high_risk_bias=0.1)
            amount = round(self.rng.uniform(20, 500), 8)  # very large
            records.append(Transaction(
                timestamp=self._timestamp_at(t),
                src_ip=self._random_public_ip(src_country),
                dst_ip=self._random_public_ip(country),
                src_port=self.rng.randint(1024, 65535),
                dst_port=self.rng.choice(BITCOIN_PORTS_NORMAL),
                txid=self._make_txid(),
                input_addresses="|".join(self._sample_addresses(self.rng.randint(1, 4))),
                output_addresses=self._make_address(),
                num_inputs=self.rng.randint(1, 4), num_outputs=1,
                amount_btc=amount,
                fee_btc=round(self.rng.uniform(0.0001, 0.0005), 8),  # oddly low fee for the value
                fee_rate_sat_vb=round(self.rng.uniform(1, 4), 2),
                country=country, asn=asn, asn_org=org,
                label="anomalous", anomaly_type="high_value_single_hop",
            ))
        return records

    def gen_peeling_chain(self, n_chains: int, base_t: float) -> List[Transaction]:
        records = []
        for c in range(n_chains):
            t = base_t + self.rng.uniform(0, 10000)
            country, asn, org = self._pick_country_asn(high_risk_bias=0.5)
            src_ip = self._burst_actor_ip(f"peel_{c}", country)
            remaining = round(self.rng.uniform(5, 50), 8)
            current_addr = self._make_address()
            chain_len = self.rng.randint(10, 40)
            for i in range(chain_len):
                if remaining < 0.001:
                    break
                t += self.rng.uniform(60, 900)  # minutes apart, evades naive rate limits
                peel = round(remaining * self.rng.uniform(0.02, 0.08), 8)
                remaining = round(remaining - peel, 8)
                next_addr = self._make_address()
                dst_country, dst_asn, dst_org = self._pick_country_asn(high_risk_bias=0.5)
                records.append(Transaction(
                    timestamp=self._timestamp_at(t),
                    src_ip=src_ip, dst_ip=self._random_public_ip(dst_country),
                    src_port=self.rng.randint(1024, 65535),
                    dst_port=self.rng.choice(BITCOIN_PORTS_NORMAL),
                    txid=self._make_txid(),
                    input_addresses=current_addr,
                    output_addresses=f"{next_addr}|{next_addr}",  # peel + change, same addr style
                    num_inputs=1, num_outputs=2,
                    amount_btc=peel, fee_btc=round(peel * 0.001, 8),
                    fee_rate_sat_vb=round(self.rng.uniform(5, 20), 2),
                    country=country, asn=asn, asn_org=org,
                    label="anomalous", anomaly_type="peeling_chain",
                ))
                current_addr = next_addr
        return records

    def gen_anomalous_port(self, n: int, base_t: float) -> List[Transaction]:
        records = []
        for _ in range(n):
            t = base_t + self.rng.uniform(0, 20000)
            country, asn, org = self._pick_country_asn(high_risk_bias=0.5)
            records.append(Transaction(
                timestamp=self._timestamp_at(t),
                src_ip=self._random_public_ip(country),
                dst_ip=self._random_public_ip(self.rng.choice(HIGH_RISK_COUNTRIES)),
                src_port=self.rng.choice(UNUSUAL_PORTS),
                dst_port=self.rng.choice(UNUSUAL_PORTS),
                txid=self._make_txid(),
                input_addresses="|".join(self._sample_addresses(self.rng.randint(1, 2))),
                output_addresses="|".join(self._sample_addresses(self.rng.randint(1, 2))),
                num_inputs=1, num_outputs=1,
                amount_btc=round(self.rng.uniform(0.01, 2), 8),
                fee_btc=round(self.rng.uniform(0.00001, 0.0005), 8),
                fee_rate_sat_vb=round(self.rng.uniform(1, 15), 2),
                country=country, asn=asn, asn_org=org,
                label="anomalous", anomaly_type="anomalous_port_usage",
            ))
        return records

    def gen_fee_anomaly(self, n: int, base_t: float) -> List[Transaction]:
        records = []
        for _ in range(n):
            t = base_t + self.rng.uniform(0, 20000)
            country, asn, org = self._pick_country_asn(high_risk_bias=0.25)
            amount = round(self.rng.uniform(0.01, 3), 8)
            if self.rng.random() < 0.5:
                # absurdly high fee (possible mixing-fee / miner-collusion signal)
                fee_rate = round(self.rng.uniform(500, 3000), 2)
            else:
                # near-zero fee on a large transaction (stuck / RBF-abuse signal)
                fee_rate = round(self.rng.uniform(0.01, 0.5), 2)
            vbytes = 200
            fee_btc = round((fee_rate * vbytes) / 1e8, 8)
            records.append(Transaction(
                timestamp=self._timestamp_at(t),
                src_ip=self._random_public_ip(country),
                dst_ip=self._random_public_ip(country),
                src_port=self.rng.randint(1024, 65535),
                dst_port=self.rng.choice(BITCOIN_PORTS_NORMAL),
                txid=self._make_txid(),
                input_addresses="|".join(self._sample_addresses(1)),
                output_addresses="|".join(self._sample_addresses(1)),
                num_inputs=1, num_outputs=1,
                amount_btc=amount, fee_btc=fee_btc, fee_rate_sat_vb=fee_rate,
                country=country, asn=asn, asn_org=org,
                label="anomalous", anomaly_type="fee_anomaly",
            ))
        return records

    def gen_geo_velocity(self, n_pairs: int, base_t: float) -> List[Transaction]:
        """Same wallet address transacting from two geographically distant
        IP/country pairs within an implausibly short window."""
        records = []
        for _ in range(n_pairs):
            t = base_t + self.rng.uniform(0, 20000)
            addr = self._make_address()
            c1 = self.rng.choice(NORMAL_COUNTRIES + HIGH_RISK_COUNTRIES)
            remaining = [c for c in (NORMAL_COUNTRIES + HIGH_RISK_COUNTRIES) if c != c1]
            c2 = self.rng.choice(remaining)
            asn1, org1 = self.rng.choice(COUNTRY_ASN_POOL[c1])
            asn2, org2 = self.rng.choice(COUNTRY_ASN_POOL[c2])
            gap = self.rng.uniform(30, 300)  # seconds — too fast for real travel
            for i, (country, asn, org) in enumerate([(c1, asn1, org1), (c2, asn2, org2)]):
                tt = t + i * gap
                records.append(Transaction(
                    timestamp=self._timestamp_at(tt),
                    src_ip=self._random_public_ip(country),
                    dst_ip=self._random_public_ip(country),
                    src_port=self.rng.randint(1024, 65535),
                    dst_port=self.rng.choice(BITCOIN_PORTS_NORMAL),
                    txid=self._make_txid(),
                    input_addresses=addr,
                    output_addresses="|".join(self._sample_addresses(1)),
                    num_inputs=1, num_outputs=1,
                    amount_btc=round(self.rng.uniform(0.001, 0.5), 8),
                    fee_btc=round(self.rng.uniform(0.00001, 0.0002), 8),
                    fee_rate_sat_vb=round(self.rng.uniform(5, 30), 2),
                    country=country, asn=asn, asn_org=org,
                    label="anomalous", anomaly_type="geo_velocity_impossible_travel",
                ))
        return records

    # ---- orchestration ------------------------------------------------------

    def generate(self, n_normal: int, n_anomalous: int) -> List[Transaction]:
        normal = self.generate_normal(n_normal)
        span = n_normal * 45.0  # rough total normal-traffic span in seconds

        # split the anomalous budget across categories
        weights = {
            "rapid_fire_layering": 0.20,
            "dust_attack": 0.15,
            "high_value_single_hop": 0.15,
            "peeling_chain": 0.15,
            "anomalous_port_usage": 0.15,
            "fee_anomaly": 0.10,
            "geo_velocity_impossible_travel": 0.10,
        }
        anomalous: List[Transaction] = []

        budget = n_anomalous
        # cluster-style anomalies: convert a tx budget into cluster counts
        rfl_budget = int(n_anomalous * weights["rapid_fire_layering"])
        anomalous += self.gen_rapid_fire_layering(
            n_clusters=max(1, rfl_budget // 35), base_t=span * 0.1)

        dust_budget = int(n_anomalous * weights["dust_attack"])
        anomalous += self.gen_dust_attack(
            n_clusters=max(1, dust_budget // 150), base_t=span * 0.25)

        hv_budget = int(n_anomalous * weights["high_value_single_hop"])
        anomalous += self.gen_high_value_single_hop(n=max(1, hv_budget), base_t=span * 0.4)

        peel_budget = int(n_anomalous * weights["peeling_chain"])
        anomalous += self.gen_peeling_chain(
            n_chains=max(1, peel_budget // 25), base_t=span * 0.55)

        port_budget = int(n_anomalous * weights["anomalous_port_usage"])
        anomalous += self.gen_anomalous_port(n=max(1, port_budget), base_t=span * 0.7)

        fee_budget = int(n_anomalous * weights["fee_anomaly"])
        anomalous += self.gen_fee_anomaly(n=max(1, fee_budget), base_t=span * 0.8)

        geo_budget = int(n_anomalous * weights["geo_velocity_impossible_travel"])
        anomalous += self.gen_geo_velocity(
            n_pairs=max(1, geo_budget // 2), base_t=span * 0.9)

        all_records = normal + anomalous
        self.rng.shuffle(all_records)
        # re-sort by timestamp so the final dataset reads as a plausible
        # chronological network log (a real capture would be time-ordered)
        all_records.sort(key=lambda r: r.timestamp)
        return all_records


# --------------------------------------------------------------------------
# I/O helpers
# --------------------------------------------------------------------------

def write_csv(records: List[Transaction], path: str) -> None:
    if not records:
        return
    fieldnames = list(asdict(records[0]).keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in records:
            writer.writerow(asdict(r))


def write_jsonl(records: List[Transaction], path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(asdict(r)) + "\n")


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Synthetic Bitcoin transaction dataset generator (PS 26146)")
    parser.add_argument("--n-normal", type=int, default=8000,
                         help="number of normal transactions to generate")
    parser.add_argument("--n-anomalous", type=int, default=800,
                         help="approximate number of anomalous transactions to generate")
    parser.add_argument("--seed", type=int, default=42, help="random seed for reproducibility")
    parser.add_argument("--out", type=str, default="btc_synthetic_dataset.csv",
                         help="output file path (.csv or .jsonl)")
    args = parser.parse_args()

    gen = BitcoinDatasetGenerator(seed=args.seed)
    records = gen.generate(n_normal=args.n_normal, n_anomalous=args.n_anomalous)

    if args.out.endswith(".jsonl"):
        write_jsonl(records, args.out)
    else:
        write_csv(records, args.out)

    n_anom = sum(1 for r in records if r.label == "anomalous")
    print(f"Generated {len(records)} transactions "
          f"({len(records) - n_anom} normal, {n_anom} anomalous) -> {args.out}")
    print(f"Seed: {args.seed} (deterministic — rerun with the same seed to reproduce)")

    # print a per-category breakdown
    from collections import Counter
    counts = Counter(r.anomaly_type for r in records if r.label == "anomalous")
    for k, v in counts.most_common():
        print(f"  - {k}: {v}")


if __name__ == "__main__":
    main()
