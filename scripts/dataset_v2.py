"""Dataset v2 scenarios. Integer accounting, not a UTXO ledger or GeoIP service."""
from collections import Counter
from dataclasses import dataclass, asdict
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
from pathlib import Path

if __package__:
    from .btc_synthetic_dataset_generator import BitcoinDatasetGenerator, Transaction, COUNTRY_ASN_POOL, UNUSUAL_PORTS, BITCOIN_PORTS_NORMAL
else:
    from btc_synthetic_dataset_generator import BitcoinDatasetGenerator, Transaction, COUNTRY_ASN_POOL, UNUSUAL_PORTS, BITCOIN_PORTS_NORMAL

SAT = 100_000_000
CATEGORIES = ("rapid_fire_layering", "dust_attack", "high_value_single_hop", "peeling_chain",
              "anomalous_port_usage", "fee_anomaly", "geo_velocity_impossible_travel")
WEIGHTS = (20, 15, 15, 15, 15, 10, 10)


@dataclass
class TransactionV2(Transaction):
    input_addresses: list
    output_addresses: list
    input_amounts: list
    output_amounts: list


def budgets(total):
    counts = [total * weight // 100 for weight in WEIGHTS]
    order = sorted(range(7), key=lambda i: (-(total * WEIGHTS[i] % 100), i))
    for i in order[:total - sum(counts)]:
        counts[i] += 1
    # Keep complete pairs; move isolated cluster rows to a singleton category.
    if counts[6] % 2:
        counts[6] -= 1
        counts[2] += 1
    for i in (0, 1, 3):
        if counts[i] == 1:
            counts[i] = 0
            counts[2] += 1
    return dict(zip(CATEGORIES, counts))


class BitcoinDatasetV2Generator(BitcoinDatasetGenerator):
    def __init__(self, seed=42, start_time=None):
        super().__init__(seed, start_time)
        self.ground_truth = []
        self._serial = 0
        self._scenario_serial = 0
        # Shared observer pool: no labels, actors or wallet ownership encoded in IPs.
        countries = list(COUNTRY_ASN_POOL)
        self.observers = []
        used = set()
        for i in range(280):
            country = countries[i % len(countries)]
            ip = self._random_public_ip(country)
            while ip in used:
                ip = self._random_public_ip(country)
            used.add(ip)
            self.observers.append((ip, country, 64512 + i, f"SYNTHETIC-NET-{i:03d}"))
        self.actors = []
        for i in range(600):
            start = self.rng.randint(0, 3 * 86400)
            end = self.rng.randint(7 * 86400, 14 * 86400)
            self.actors.append({"id": f"actor-{i:04d}", "addresses": self._address_pool[4*i:4*i+4],
                                "start": start, "end": end,
                                "sessions": [self.rng.randint(start, end-40000) for _ in range(self.rng.randint(3, 15))],
                                "scale": self.rng.lognormvariate(0, 0.8)})
        self.weights = [self.rng.lognormvariate(0, 1.1) for _ in self.actors]

    def _actor(self):
        return self.rng.choices(self.actors, weights=self.weights, k=1)[0]

    def _time(self, actor):
        if self.rng.random() < 0.65:
            t = self.rng.choice(actor["sessions"]) + int(self.rng.expovariate(1 / 180))
        else:
            t = self.rng.randint(actor["start"], actor["end"]-40000)
        return min(t, actor["end"]-40000)

    def _scenario(self):
        self._scenario_serial += 1
        return hashlib.sha256(f"scenario:{self.seed}:{self._scenario_serial}".encode()).hexdigest()[:20]

    def _address(self, actor=None):
        if actor is not None and self.rng.random() < 0.94:
            return self.rng.choice(actor["addresses"])
        return self._make_address()

    def _amount(self, actor):
        p = self.rng.random()
        if p < 0.07:
            return self.rng.randint(546, 4000)
        if p < 0.14:
            return self.rng.randint(5 * SAT, 600 * SAT)
        return max(1, min(600 * SAT, int(self.rng.lognormvariate(-2.5, 1.6) * actor["scale"] * SAT)))

    def _fee(self, ni, no, extreme=False):
        p = self.rng.random()
        if extreme:
            rate = self.rng.uniform(0.05, 2) if p < 0.5 else self.rng.uniform(200, 3000)
        elif p < 0.10:
            rate = self.rng.uniform(0.05, 2)
        elif p < 0.20:
            rate = self.rng.uniform(100, 3000)
        else:
            rate = self.rng.uniform(8, 60)
        return int((Decimal(str(rate)) * self._estimate_vbytes(ni, no)).quantize(Decimal(1), rounding=ROUND_HALF_UP))

    def _split(self, total, count):
        weights = [self.rng.randint(1, 1000) for _ in range(count)]
        amounts = [total * w // sum(weights) for w in weights]
        for i in range(total-sum(amounts)):
            amounts[i % count] += 1
        return amounts

    def _emit(self, actor, scenario, t, inputs, outputs, output_sats, fee, category="", input_sats=None, observer=None):
        total = sum(output_sats)
        input_sats = input_sats if input_sats is not None else self._split(total + fee, len(inputs))
        assert total > 0 and min(input_sats + output_sats + [fee]) >= 0
        assert sum(input_sats) == total + fee
        assert len(inputs) == len(input_sats) and len(outputs) == len(output_sats)
        observer = observer or self.rng.choice(self.observers)
        dst = self.rng.choice(self.observers)
        # Normal traffic also uses the full unusual-port set.
        unusual = category == "anomalous_port_usage" or self.rng.random() < 0.12
        src_port = self.rng.choice(UNUSUAL_PORTS) if unusual and self.rng.random() < 0.5 else self.rng.randint(1024, 65535)
        dst_port = self.rng.choice(UNUSUAL_PORTS) if unusual else self.rng.choice(BITCOIN_PORTS_NORMAL)
        self._serial += 1
        txid = hashlib.sha256(f"transaction:{self.seed}:{self._serial}".encode()).hexdigest()
        label = "anomalous" if category else "normal"
        self.ground_truth.append({"txid": txid, "label": label, "anomaly_type": category,
                                  "scenario_id": scenario, "actor_id": actor["id"]})
        return TransactionV2(self._timestamp_at(t), observer[0], dst[0], src_port, dst_port, txid,
                             inputs, outputs, len(inputs), len(outputs), total/SAT, fee/SAT,
                             round(fee/self._estimate_vbytes(len(inputs),len(outputs)), 2),
                             observer[1], observer[2], observer[3], label, category,
                             [v/SAT for v in input_sats], [v/SAT for v in output_sats])

    def _payment(self, actor, scenario, t, category="", observer=None, sender=None):
        ni = self.rng.choice([1, 1, 2, 3])
        no = self.rng.choice([1, 2, 2, 3])
        inputs = [sender or self._address(actor) for _ in range(ni)]
        outputs = [self._address(self._actor())]
        outputs += [self._address(actor) for _ in range(no-1)]
        total = self._amount(actor)
        if category == "high_value_single_hop":
            total = self.rng.randint(5 * SAT, 600 * SAT)
            outputs = outputs[:1]
            no = 1
        fee = self._fee(ni, no, category == "fee_anomaly")
        return self._emit(actor, scenario, t, inputs, outputs, self._split(total, no), fee, category, observer=observer)

    def _partition(self, count, minimum, maximum):
        if not count:
            return []
        # Whole scenarios sized in advance; no generated transactions are truncated.
        n = max(1, (count + maximum - 1)//maximum)
        lengths = [count//n + (i < count % n) for i in range(n)]
        if min(lengths) < minimum:
            if count < minimum:
                return [count]  # budget allocation already prevents singleton clusters
            raise ValueError("budget cannot form complete scenarios")
        self.rng.shuffle(lengths)
        return lengths

    def generate(self, n_normal=15300, n_anomalous=2700):
        if any(isinstance(n, bool) or not isinstance(n, int) or n < 0 for n in (n_normal, n_anomalous)):
            raise ValueError("record counts must be nonnegative integers")
        records = []
        for _ in range(n_normal):
            actor = self._actor()
            records.append(self._payment(actor, self._scenario(), self._time(actor)))
        for category, count in budgets(n_anomalous).items():
            if category in ("high_value_single_hop", "anomalous_port_usage", "fee_anomaly"):
                for _ in range(count):
                    actor = self._actor()
                    records.append(self._payment(actor, self._scenario(), self._time(actor), category))
                continue
            maximum = {"rapid_fire_layering": 30, "dust_attack": 90, "peeling_chain": 25,
                       "geo_velocity_impossible_travel": 2}[category]
            for length in self._partition(count, 2, maximum):
                actor, scenario = self._actor(), self._scenario()
                t = self._time(actor)
                current = self._address(actor)
                observer = self.rng.choice(self.observers)
                # Chain funding is carried forward exactly, including fees.
                remaining = self.rng.randint(1 * SAT, 50 * SAT)
                if category == "rapid_fire_layering":
                    remaining = self.rng.randint(1_000_000, 10_000_000)
                for i in range(length):
                    if category == "geo_velocity_impossible_travel":
                        if i:
                            observer = self.rng.choice([o for o in self.observers if o[1] != observer[1]])
                        records.append(self._payment(actor, scenario, t, category, observer, current))
                        t += self.rng.randint(30, 300)
                    elif category == "dust_attack":
                        outputs = [self._address(self._actor()) for _ in range(self.rng.randint(1, 3))]
                        amounts = [self.rng.randint(546, 4000) for _ in outputs]
                        records.append(self._emit(actor, scenario, t, [current], outputs, amounts,
                                                  self._fee(1, len(outputs)), category, observer=observer))
                        t += self.rng.randint(0, 2)
                    else:
                        no = 2 if category == "peeling_chain" else 1
                        fee = min(self._fee(1, no), max(0, remaining//1000))
                        if no == 2:
                            peel = max(1, remaining * self.rng.randint(2, 8)//100)
                            amounts = [peel, remaining - fee - peel]
                            outputs = [self._address(self._actor()), self._make_address()]
                        else:
                            amounts, outputs = [remaining-fee], [self._make_address()]
                        records.append(self._emit(actor, scenario, t, [current], outputs, amounts,
                                                  fee, category, [remaining], observer))
                        remaining, current = amounts[-1], outputs[-1]
                        t += self.rng.randint(60, 900) if no == 2 else self.rng.randint(1, 3)
        records.sort(key=lambda r: (r.timestamp, r.txid))
        order = {r.txid: i for i, r in enumerate(records)}
        self.ground_truth.sort(key=lambda r: order[r["txid"]])
        assert len(records) == n_normal + n_anomalous
        return records

    def write_metadata(self, records, out, files):
        out = Path(out)
        truth = out.with_suffix(".ground_truth.jsonl")
        truth.write_text(''.join(json.dumps(r, sort_keys=True) + "\n" for r in self.ground_truth), encoding="utf-8")
        manifest = {"schema_version": 2, "seed": self.seed, "normal": sum(r.label == "normal" for r in records),
                    "anomalous": sum(r.label == "anomalous" for r in records), "records": len(records),
                    "anomaly_distribution": dict(Counter(r.anomaly_type for r in records if r.anomaly_type)),
                    "amount_convention": "amount_btc=sum(output_amounts), including change; inputs=outputs+fee",
                    "accounting": "integer satoshis; no UTXO ledger", "network": "synthetic observer mappings, not GeoIP or ownership",
                    "scenario_count": len({r["scenario_id"] for r in self.ground_truth}),
                    "files": {Path(f).name: hashlib.sha256(Path(f).read_bytes()).hexdigest() for f in [*files, truth]}}
        out.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True)+"\n", encoding="utf-8")
