# Deterministic presentation walkthrough

Use the existing development dataset and frozen tuned-42 artifact. Start with
the commands in [dashboard.md](dashboard.md). No generation or training is needed.

1. Open http://127.0.0.1:8000 and wait for **Offline · Ready**. Counts are calculated
   from the current graph. Explain that the observations are synthetic.
2. Click the first investigation lead. With the default files it is
   `6438536fd7ddeb015a2a0a7e5cc5f0d2df04d600d9ea0592c9fa3f1a41db3202`.
   Inspect its score, frozen threshold, fee/output counts and network context.
   A flag is an investigative lead, not a crime probability.
3. Choose two hops, then three. Select an address circle and inspect its counts,
   observed amounts and timeline. **Expand selected** follows that address.
   One connected address for the first lead is
   `1ESbdF6ACUgGWDe9fvPjeisQRNLWvzPJtE`.
4. Demonstrate search with that exact address or a partial TXID. Partial results
   require selection; no-result searches report an empty result explicitly.

## Why sequence investigation adds value

The following example was selected using evaluation-only scenario metadata in
the earlier graph verification. It is **not a model discovery**. Runtime API/UI
payloads do not contain category, actor or scenario labels. Explain this aloud.

Search the start transaction:

```text
c03fa0edd88742770a0d009c75c20f5d979dd2ae1d4ef22203f390aed54c0f46
```

Click **Set selected as trace start**. Search the endpoint:

```text
3ca9331ae6d7bbb004e69a8f7ef31114e4b034954a3b4d33536d4ac2ef7e913e
```

Click **Trace to selected**. The existing chronological backend reconstructs
30 address-linked transactions within 58 seconds, displayed as 59 nodes and
58 directed relationships. Inspect the ordered timeline for individual amounts,
timestamps and scores. Many sequence members fall below the frozen threshold;
do not describe them as ML detections. This illustrates why temporal graph
inspection complements the weaker transaction-only sequence recall.

Select nodes along the path to inspect details, then expand a selected node to
return to a neighbourhood. Recenter resets zoom/pan. Highlighting means a possible
address-linked chronological path, not verified UTXO spends or common ownership.

Dense views may hit node/edge/search bounds. The UI explicitly reports this;
follow shorter segments when needed. The historical long peeling path reached
the search-state bound; that limitation is retained, not concealed or retuned.
