# Drone demo verification — 22 October 2026

## Observed live run

The browser submitted an eight-unit O-negative request for H1 at the initial snapshot. Two actual Decisions API calls selected four-unit B1→H1 deliveries. The browser showed reservation, flight and arrival; both drones ended at H1 and the request reached 8/8 fulfilled. The full weekend then ran through the local HTTP API.

| Measure | Live Decisions controller | Algorithm-only controller |
|---|---:|---:|
| Requested units | 469 | 469 |
| Fulfilled before deadline | 392 | 392 |
| Unmet at deadline | 77 | 77 |
| Completed drone missions | 76 | 76 |
| Remaining available units | 397 | 397 |
| Reserved / in transit at end | 0 / 0 | 0 / 0 |
| API attempts / successful responses | 98 / 98 | 0 / 0 |
| Algorithm fallbacks | 0 | 0 |

The final live run used `gpt-6-luna` and 313,722 input tokens. It made 65 model transfer choices and 33 model social assessments. Three exact quoted reposts used deterministic suppression. Eleven transfers had only one feasible option and executed by deterministic policy. All 76 selections belonged to the offered feasible set; 73 selected the same first-ranked option as the deterministic ranking at that decision's state. The outcome comparison uses identical incoming events, including the initial browser request, not identical intermediate states.

There are 337 recorded frames, 36 social reports, and a final reconciled unit ledger. All missions respected their four-unit payload and request deadline. No unit was consumed twice or committed to overlapping missions. Real elapsed time and Europe/Paris display offsets cross the Sunday clock change. The synthetic shortage is retained; available stock elsewhere does not establish timely fulfilment under reserves and fleet capacity. H4's 16-unit A-positive emergency request was fulfilled by four B1 deliveries while B2→H4 was unavailable.

## Issues found and corrected

1. An early live run sent a `choice` question with one option. The API returned HTTP 400. The application correctly marked its fallback, and the test stopped. The API contract requires 2–255 choices. The controller now directly executes a sole feasible plan and has a regression test for that boundary. The failed run's receipts remain separate under `runs/drone-live-v1/`.
2. Rapid sequential HTTP requests exposed a short interval where the response had been sent but the transaction lock was still held. The handler now releases its lock before sending a successful response. Concurrent actions still receive an explicit 409 response. The verification driver retries that busy response without repeating a completed event.
3. In the intermediate completed run, a Lyon report received an urgent Paris review flag. The final controller asks a separate location question and applies the explicit Paris scope policy. Model and adjusted flags remain distinct. All reports starting with Lyon or Nantes were suppressed in the final live run. This does not establish general social classification accuracy.

The final successful complete run is `runs/drone-live-v3/`. It preserves actual API receipts, replay frames and the final state. The comparison baseline is `runs/drone-baseline-comparison-v3/`. Local runs are ignored by Git; the handoff archive includes the successful replay and receipts separately. The intermediate completed run remains under `runs/drone-live-v2/`. The original historical social benchmark is unchanged.

## Scope

Final checks: all 45 automated tests passed; canonical validation and all nine raw-source hashes passed; JavaScript syntax and Git whitespace checks passed. Browser checks covered request injection, reservation, flight, receipt, recorded timeline seeking, play/pause, return to live and starting a fresh run. The fresh run returned to 777 available units and zero requests and calls. No browser warning or error logs were observed. A 320-pixel viewport check found no horizontal page overflow. These checks are not a formal accessibility audit.

The [v1.0.0 release bundle](https://github.com/benlewis-beyondthought/blood-in-motion/releases/tag/v1.0.0) contains `recorded-demo/replay.json`, `api-receipts.jsonl`, `final-state.json` and `verification.json`. Start the local server, then use **Open saved replay** to load that replay without API calls. A compact [verification summary](evidence/dispatch-live-summary.json) is also committed in this repository.

This proves the synthetic browser → server → Decisions API → validated plan → unit reservation → drone flight → arrival → request fulfilment path. It does not prove optimal scheduling, better decisions than the algorithm, real patient outcomes, clinically valid reserves, actual flight feasibility or validated blood transport. Social flags are report-level investigation decisions; there is no numerical social-to-blood conversion.

The source implementation and automated tests are in `blood_response/dispatch.py`, `blood_response/decisions.py`, `blood_response/dispatch_server.py`, `blood_response/web/` and `tests/test_dispatch.py`. Run `python -m unittest discover -s tests -v` and `python -m blood_response validate` from the repository root.
