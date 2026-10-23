# Shortage diagnostics and rolling-horizon planning

The new default CLI scheduler is a deterministic, bounded 90-minute lookahead. It uses the existing simulator and feasibility checks, with no new dependency. It is not a global optimization solver. The existing greedy algorithm and live Decisions transfer controller remain available explicitly.

```powershell
# New scheduler, no paid calls
python -m blood_response.dispatch_server --scheduler rolling --port 8879 --output runs/my-lookahead

# Existing model-selected individual transfers
python -m blood_response.dispatch_server --scheduler greedy --controller decisions --prompt-key --output runs/my-live-transfers

# Lookahead scheduling with live social classification only
python -m blood_response.dispatch_server --scheduler rolling --controller decisions --prompt-key --output runs/my-live-social

# Paired weekend comparison, including the original eight-unit manual request
python tools/compare_schedulers.py --output runs/my-comparison
```

## What changes

The rolling controller first consumes eligible local stock for current requests. It then tests at most 12 initial transfer actions: the first two feasible plans per request, in existing priority/deadline order. Each action is simulated forward for 90 minutes with greedy continuation. It maximizes delivered critical units, then scheduled units, then routine units, then minimizes flight distance. Stable ties keep candidate order. Only the initial action is committed; all feasibility checks run again. It repeats for remaining idle drones and replans after incoming events. Airborne missions remain committed.

The search can choose a different request or source from the greedy baseline. It does not search every sequence, include a deliberate wait action, pre-position drones without requests, or guarantee improvement on every scenario. Predictions depend on this bounded candidate set and greedy continuation. Historical fulfilled units are subtracted before scoring. Previously committed deliveries arriving inside the horizon are included equally in the alternative projections.

Future visibility is deliberately limited. The planner sees current requests, current missions, their scheduled events, expiry and published planned procedure requests within the horizon. It cannot see unreleased emergency requests, social posts, future closures, reopening times or stock receipts from the scripted event queue. Residual background releases are excluded from the lookahead rather than treated as certain advance knowledge. The synthetic daily planned activity remains known calendar information. Forecasts stop at the horizon and at the scenario end.

The numerical scheduler does not call an LLM. With `--controller decisions`, social reports still use the real Decisions API; `--scheduler greedy` retains the previous model transfer selection path. Lookahead projections and what-if comparisons always use isolated algorithm-only copies with no client or credential. They never make paid calls.

## Why this plan?

The panel shows the latest selected action, evaluation time, horizon, objective, projected fulfilment by priority and projected flight distance. It compares the chosen continuation with the greedy first action from the same planning state. Expand the alternatives to inspect every tested initial action. These are computed projections, not model-written rationales or a claim that the future is known.

## What would help?

For unresolved requests, diagnostics show the observed time, uncommitted units, deliveries already committed, available stock by donor, protected reserves, busy drones, route restrictions and deadline/mission limits. Flags can overlap. A protected reserve flag means some stock is protected, not that lowering the reserve would solve the request. Missed requests retain the last pre-deadline diagnostic; the panel displays its timestamp.

The comparison starts from the first unresolved snapshot saved for that request, after dispatches already committed at that instant. It tests four independent continuations: no change; one additional drone at B1; one additional drone at B2; and eight already-processed usable units received immediately at the requesting hospital. Each uses the same known events and greedy continuation until the original request deadline. It reports target fulfilment and changes in system fulfilment by priority, so a benefit to one request is not silently treated as a system benefit.

These are hypothetical resource changes, not a donation forecast, an operational recommendation or retrospective causal proof. An extra drone cannot fix a deadline shorter than travel time. New stock may help only if it is usable before the deadline. Unknown later events are excluded, so a projection can differ from the subsequent actual replay. The comparison never changes live stock, missions, requests or the clock. It saves only its report, which is included in subsequent replay frames. Recorded mode displays saved reports but cannot start a new comparison.

## Verification

Observed paired weekend run (22 October 2026, `runs/scheduler-comparison-v4/`):

| Measure | Existing greedy baseline | Rolling lookahead |
|---|---:|---:|
| Requested units | 469 | 469 |
| Fulfilled by deadline | 392 | 398 |
| Unmet units | 77 | 71 |
| Critical unmet units | 47 | 47 |
| Routine unmet units | 30 | 24 |
| Requests with any deadline shortfall | 14 | 15 |
| Delivered missions | 76 | 76 |
| Reserved / in transit at end | 0 / 0 | 0 / 0 |
| API calls | 0 | 0 |

The six-unit gain is in routine fulfilment. Critical shortages are unchanged, and one more request has some unmet demand. This reflects the objective of maximizing units, not maximizing fully completed requests. It is not evidence of general superiority, clinical benefit or better model judgment. Both ledgers passed conservation checks; identical incoming requests and unchanged canonical hashes were verified. The original API-controlled baseline had the same 392/469 aggregate outcome, but this new comparison did not rerun the model.

On this host the full measured event loop took approximately 14 seconds for greedy and 80 seconds for rolling, with other verification work running concurrently. These are indicative elapsed run times, not latency guarantees. A performance fix removes unused UI snapshot construction from internal rollouts and indexes available inventory within those isolated copies; actual live event frames and all conservation checks remain enabled.

`tests/test_planning.py` covers future-event isolation, source-state preservation, counterfactual isolation, pre-deadline diagnostic retention, the HTTP endpoint and a constructed competing-request case where lookahead serves four critical units and greedy serves one. This focused case establishes that lookahead can change the allocation; it does not estimate typical improvement.

`tools/compare_schedulers.py` runs both controllers with identical requests, checks canonical hashes, asserts the established 392/469 greedy baseline and exports both ledgers and replays with a machine-readable comparison. All operational conservation assertions remain enabled in hypothetical rollouts and real execution. Original social API evidence and canonical/raw datasets remain separate and unchanged.

Final checks: all 53 regression tests passed, including eight new planning tests. Canonical validation and all raw-source hashes passed. JavaScript syntax and whitespace checks passed. Browser checks exercised dispatch, shortage creation, the what-if HTTP action and the resulting panels. A 320-pixel viewport had no horizontal page overflow; no browser warning/error logs were observed. This is not a formal accessibility audit.

The [v1.0.0 release bundle](https://github.com/benlewis-beyondthought/blood-in-motion/releases/tag/v1.0.0) places the paired replays and final ledgers under `recorded-scheduler/greedy/` and `recorded-scheduler/rolling/`, with `recorded-scheduler/comparison.json`. The [comparison summary](evidence/scheduler-comparison.json) is also committed here. Load either replay through **Open saved replay** after starting the server. The earlier real API run remains under `recorded-demo/` and is distinct from this deterministic scheduler comparison.
