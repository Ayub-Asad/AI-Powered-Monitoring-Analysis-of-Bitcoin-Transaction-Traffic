"""Graph contract v1; identifiers are namespaced, never wallet ownership claims."""
from dataclasses import dataclass, field
import pandas as pd

VERSION = 'bitcoin-investigation-v1'
SEMANTIC_CATEGORIES = ('transaction_normal', 'transaction_flagged', 'transaction_unscored',
                       'address', 'network_context', 'selected', 'path_highlight')


def node_id(kind, identifier):
    if kind not in ('transaction', 'address'):
        raise ValueError('entity type must be transaction or address')
    return f'{kind}:{identifier}'


def utc(value):
    stamp = pd.Timestamp(value)
    if pd.isna(stamp) or stamp.tzinfo is None:
        raise ValueError('timestamp must be timezone-aware')
    return stamp.tz_convert('UTC').isoformat(timespec='nanoseconds')


@dataclass(frozen=True)
class Limits:
    max_nodes: int = 250
    max_edges: int = 500
    max_expansions: int = 10000

    def __post_init__(self):
        for name in ('max_nodes', 'max_edges', 'max_expansions'):
            value = getattr(self, name)
            if type(value) is not int or value < 1:
                raise ValueError(f'{name} must be a positive integer')


@dataclass(frozen=True)
class TransactionFilter:
    flagged_only: bool = False
    min_anomaly_score: float | None = None
    start: str | None = None
    end: str | None = None
    min_amount_satoshis: int | None = None

    def __post_init__(self):
        import math
        if self.min_anomaly_score is not None and not math.isfinite(self.min_anomaly_score):
            raise ValueError('score filter must be finite')
        if self.min_amount_satoshis is not None and (type(self.min_amount_satoshis) is not int or self.min_amount_satoshis < 0):
            raise ValueError('minimum amount must be nonnegative integer satoshis')
        for name in ('start', 'end'):
            if getattr(self, name) is not None:
                object.__setattr__(self, name, utc(getattr(self, name)))
        if self.start and self.end and self.start > self.end:
            raise ValueError('start must precede end')

    def matches(self, node):
        if node['type'] != 'transaction':
            return True
        score = node['anomaly_score']
        return (not self.flagged_only or node['flagged'] is True) and (
            self.min_anomaly_score is None or score is not None and score >= self.min_anomaly_score
        ) and (self.start is None or node['timestamp'] >= self.start) and (
            self.end is None or node['timestamp'] <= self.end
        ) and (self.min_amount_satoshis is None or node['attributes']['amount_satoshis'] >= self.min_amount_satoshis)


@dataclass
class InvestigationGraph:
    nodes: dict = field(default_factory=dict)
    edges: dict = field(default_factory=dict)
    adjacent: dict = field(default_factory=dict)
    outgoing: dict = field(default_factory=dict)
    component_sizes: dict = field(default_factory=dict)

    def require(self, entity):
        if entity not in self.nodes:
            raise KeyError(f'unknown graph entity: {entity}')
        return entity
