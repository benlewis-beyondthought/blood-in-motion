# One chronological application flow

The combined demo uses the canonical contract introduced in merged PR #1. It does not rebuild, replace or combine the preserved source inventories. The original social fixture and recorded API results remain unchanged.

## Run and inspect

```sh
python -m pip install -r requirements.txt
python -m blood_response demo --output runs/combined-demo
```

Open `runs/combined-demo/index.html` directly in a browser. No web server, API key, database, Node installation or frontend build is needed. The file embeds the same frames saved in `demo.json`. Every run requires a new output directory.

1. Start at the assumed **22 October, 12:00** inventory snapshot. There are 777 available units. The next-day planner proposes 15 units across three routes under its existing floor, reserve and ETA assumptions. No social post is available yet.
2. Select **Next report**. Hourly inventory simulation proceeds to the latest completed tick before that post. The first forward post becomes available on **23 October at 08:31**, while inventory is explicitly labelled **08:00**. These are different clocks with different precision.
3. Continue to the gathering and injury reports on **24 October**. Select the **paris centre east** event to inspect its available evidence and H1/H2 review candidates. These candidates come from the declared coarse demo map; they are not patient destinations.
4. At **12:06**, SOC-017 raises its event to urgent review. At **12:08**, the exact repost SOC-018 is suppressed as a new alert while its event retains urgent review. Stock and forecast do not change on either social step.
5. Inspect hospital rows, expand blood groups, and inspect proposed unit IDs. The planner uses a shared bank pool within each snapshot. Proposals are not reservations or instructions to dispatch. Plans from different frames are alternatives, not cumulative commitments.
6. Continue to **25 October** for old-content and resolution messages. Resolution is a reported phase requiring review; it does not establish citywide safety or normal hospital demand. The hourly slider also includes the two separate 02:00 hours at the autumn clock change, distinguished by CEST/CET.

**Next step** includes hourly ticks. **Next report** skips display of intervening ticks while still applying them to the seeded simulation. The range control can seek backward without mutating the data. **Show all hospitals** clears the event filter. Keyboard users can use Tab, Enter/Space, the range arrow keys and native select controls.

## What is real, recorded, scripted or assumed

| Layer | Source and boundary |
|---|---|
| Starting inventory, history, planned activity and logistics | The merged six-file canonical synthetic dataset. Legacy stock remains excluded. |
| Simulated changes | Existing seeded hourly simulator, with its documented consumption, immediate-use donation and replenishment assumptions. |
| Forward social text | Existing hypothetical 23–25 October canonical fixture, not reports of verified protests on those dates. |
| Default social decisions and event grouping | Authored reference fields in canonical `expected_decisions.jsonl`, explicitly used as a scenario script. No inference or model accuracy is demonstrated. |
| Duplicate suppression, escalation, lifecycle and evidence fields | Existing deterministic `blood_response.social.normalize` policy. This is application logic, not a new model benchmark. |
| Candidate facilities | Existing declared `social_site_context.json` mapping. Fictional named institutions never acquire real site IDs. |
| Recorded Decisions API benchmark | Frozen 16–18 October replay only. It is not shifted, replayed as forward inference or rescored here. |
| Transfer proposals | Existing next-day planner. Social reports neither add demand units nor change route estimates. Unknown external ETAs remain unavailable. |

The generated summary reports no unmet hourly requests for the default seed 42 run (399 requested and used). That does not mean every next-day planning snapshot has no uncovered demand. Current hourly fulfilment, next-day forecast gaps and stock-status thresholds are distinct. This fixture does not establish a real emergency shortage.

## Optional aligned prediction input

If a separate, explicitly authorised forward inference run already exists, use its prediction file:

```sh
python -m blood_response demo --predictions runs/forward-social/baseline/predictions.json --output runs/combined-with-predictions
```

The supplied file must cover each canonical report once, in order, with exact matching availability timestamps. The shared policy rejects the unchanged historical API outputs. Matching timestamps do not authenticate a model or provider; the interface labels supplied predictions accordingly. The demo command itself makes no API calls.

The existing `run_decisions_replay.py --dataset data/canonical` is still the separate entry point for a paid forward run, should the team choose to authorise one. This feature neither invokes it nor claims new agreement scores.

## Implementation and verification

`blood_response/demo.py` merges the stock ticks and social arrivals by UTC instant, reuses `advance`, `plan`, `validate` and the shared social policy, and exports immutable presentation frames. At each report it records the stock timestamp separately. Proposals do not execute; the simulator's own logged replenishments remain independent of the proposal list.

Tests verify chronological visibility, inventory conservation, unchanged ledgers with social enabled/disabled, the Sunday clock change, correct duplicate handling and regional routing, non-duplicated proposals, preservation of source files, rejection of historical timestamps, non-overwriting export, and safe embedding of untrusted report text. The screen uses native keyboard controls and text labels alongside status colours.

Patient-level emergency requirements, clinical demand validation, verified catchments, external ETAs and real database integration remain outside this demonstration.
