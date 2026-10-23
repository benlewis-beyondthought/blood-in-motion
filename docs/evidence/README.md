# Recorded evidence

These are preserved results from 22 October 2026. They are not fresh API runs made during repository cleanup.

- [dispatch-live-summary.json](dispatch-live-summary.json): one complete forward Decisions API run compared with an algorithm-only run. Both include the same initial eight-unit manual request.
- [scheduler-comparison.json](scheduler-comparison.json): the separate greedy-versus-rolling comparison, using identical incoming requests and no paid API calls.

The root README explains the limits of these results. Detailed methods are in [DRONE-VERIFICATION.md](../DRONE-VERIFICATION.md) and [ROLLING-SCHEDULER.md](../ROLLING-SCHEDULER.md).

The v1.0.0 release bundle contains the successful operational API receipts and replay under `recorded-demo/`, and paired deterministic replays under `recorded-scheduler/`. They contain synthetic scenario content. Source credentials and local configuration are excluded.

The earlier social-only API calls and per-post traces are committed separately in [openai-decisions-replay-v1](../../openai-decisions-replay-v1/). Do not relabel those historical responses as the forward operational run.
