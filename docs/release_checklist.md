# Offline release rehearsal checklist

Linux and OS-network-disabled checks remain unchecked until actually performed.
Record date, operator, OS, Python, wheelhouse hash, browser and elapsed timings.

- [ ] Clean provisioned Linux machine; record distribution, architecture and CPython 3.13.14
- [ ] Trusted archive SHA-256 and release artifact checksums
- [ ] Network disabled at OS/VM level; record method
- [ ] Install from wheelhouse only; record elapsed time and pip check
- [ ] Application startup on 127.0.0.1:8000
- [ ] Health endpoint returns ok
- [ ] Overview shows 18,000 scored transactions
- [ ] Alerts ordered by score
- [ ] Exact and partial search
- [ ] Demo transaction 6438536fd7ddeb015a2a0a7e5cc5f0d2df04d600d9ea0592c9fa3f1a41db3202
- [ ] Transaction graph
- [ ] Address investigation: 1ESbdF6ACUgGWDe9fvPjeisQRNLWvzPJtE
- [ ] 1/2/3 hop expansion and visible truncation
- [ ] Timeline
- [ ] 30-transaction / 58-second evaluation-selected path tracing
- [ ] Network context described as synthetic observations
- [ ] Browser presentation at 1366x768, 1920x1080 and 768x900
- [ ] Browser developer tools: zero required external requests and JS exceptions
- [ ] Ctrl+C shutdown and restart; dashboard loads again
- [ ] bash verify.sh passes; save measured results

Do not describe the evaluation-selected sequence as an ML discovery.
See [offline instructions](../README_OFFLINE.md) and [demo](demo_walkthrough.md).
