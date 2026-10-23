# Paris blood distribution with simulated drones

This local application executes transfers from a shared unit ledger. The map shows four hospitals, two banks, two simulated drones, incoming requests, social reports and model-selected plans. It uses the canonical data from merged PR #1. The earlier hourly simulator and social benchmark remain separate commands.

The new default scheduler is deterministic rolling lookahead. See [shortage diagnostics and scheduling](ROLLING-SCHEDULER.md). Commands below explicitly select the original greedy transfer controller; its recorded API results remain unchanged.

## Start

From the repository root, with Python 3.12 and `pip install -r requirements.txt`:

```powershell
# Offline controller, no paid calls
python -m blood_response.dispatch_server --scheduler greedy --output runs/my-offline-run

# Live Decisions API; enter a key at the hidden terminal prompt
python -m blood_response.dispatch_server --scheduler greedy --controller decisions --prompt-key --output runs/my-live-run

# Alternatively use OPENAI_API_KEY from the environment or an explicitly named file
python -m blood_response.dispatch_server --scheduler greedy --controller decisions --env-file C:\path\to\.env --output runs/my-live-run-2

# Complete the scenario without the browser
python -m blood_response.dispatch_server --scheduler greedy --run-all --output runs/my-batch-run
```

Open http://127.0.0.1:8878/. Each invocation needs a new output directory. The server binds only to localhost. It does not write to PostgreSQL. Leaflet 1.9.4 is vendored with its license; the OpenStreetMap background tiles require internet access. Coordinates and flights remain visible if tiles fail.

The default maximum is 200 API attempts per server process, including social decisions. `--max-api-calls` changes that bound. Restarting the scenario does not reset that budget. The clock pauses while a call is in progress. The key remains server-side; request receipts contain no authorization headers. Do not put credentials in the repository or browser.

## Use the demo

1. Send the default eight-unit O-negative request for H1. If more than one plan is feasible, the live controller calls Decisions. Inspect the selected source, drone, quantity, arrival time and receipt ID.
2. Use **Next event** to move through reservation, repositioning, loading, departure, landing and receipt. **Play simulation** advances at minute intervals during missions and skips quiet periods. Pause remains available during a model call; the in-progress event finishes before playback stops.
3. Blood leaves the available pool on reservation. At departure it is in transit and has no facility location. It becomes usable at the destination after unloading. Fulfilment then consumes the exact unit IDs.
4. Friday through Sunday includes planned requests, residual background demand, independent emergency requests and 36 social reports. Saturday includes a blocked B2→H4 flight link and a deliberately difficult O-negative shortage. Sunday includes a declared stock receipt.
5. **Review this run** opens recorded frames and a seek slider. **Save replay** downloads those frames. **Open saved replay** reads an earlier exported JSON file locally. Recorded views make no API calls and disable request injection. **Return to live** resumes the current server state.
6. **New run** saves the old run and starts again from canonical inventory. Earlier runs remain under the run directory. A new run can make paid calls when the server uses the Decisions controller.

## Decision boundary

`blood_response/dispatch.py` owns the clock, inventory, reservations, pending requests, drone state, route restrictions, feasibility checks and ledger assertions. `decisions.py` owns the typed API calls and receipts. `dispatch_server.py` exposes the local application endpoints. `frontend/` contains the React and shadcn/ui source. Its production build in `blood_response/web/` renders the server state. See [interface setup](INTERFACE.md).

For each waiting request, code consumes eligible local stock, then searches all six local sites and idle drones. Donor banks retain one baseline day for their assigned hospitals. Donor hospitals retain the maximum of their baseline, the day's planned demand and current waiting requests. These conservative quantities are demo policy, not validated clinical rules. Candidates must use exact blood-group matches, stock that is unreserved and unexpired on arrival, a permitted flight link, a free drone, a payload within four units, and an arrival before the request deadline. A candidate can be a partial fulfilment.

The controller processes critical requests first, then scheduled and routine requests, with earliest deadlines first within a class. For two or more feasible plans, the Decisions API chooses a plan ID. The prompt prioritizes units delivered, then earliest arrival, then flight distance. This is a transparent per-request heuristic, not a globally optimal fleet scheduler. Code rechecks the complete selected plan against the current version before dispatch. Exactly one feasible plan executes through deterministic policy; the Decisions API requires at least two choice options. No feasible plan leaves the request waiting until a state change or its deadline.

API failures, refusals, invalid outputs and exhausted call budgets produce a visible `algorithm_fallback`. The fallback selects the first plan under the declared ranking. Such decisions are not recorded as model successes. Social failures enter REVIEW. Exact quoted reposts are suppressed in code. Other social reports receive a model review flag, evidence label and location scope using only earlier reports (the last 12 for compact context). A Paris scope policy suppresses out-of-area alerts; explicit Lyon/Nantes prefixes take precedence over an incorrect model location. Unknown locations cannot become Paris urgent alerts. Any adjusted model flag is retained alongside the application flag. This is a narrow fixture policy, not a general geocoder. This new application has report-level review flags; it does not claim the full event-clustering evaluation of the original social runner. Social reports never add blood demand or automatically change flight restrictions.

## Scenario assumptions

- The snapshot is 22 October at noon, as already declared in the canonical contract. Scheduled simulation activity begins on 23 October. The intervening hours retain stock except expiry; they do not invent partial-day demand.
- Date-only planned procedures are aggregated by hospital/group and released at 09:00 with a three-hour deadline. If any procedure in that aggregate is scheduled-critical, that aggregate has critical priority. These are invented scheduling choices.
- Residual background demand is released at 15:00: `max(0, ceil(frozen historical mean) - planned units)`. Planned plus background therefore equals the planning floor. The separately identified emergencies add demand without duplicating baseline activity. Baselines remain frozen so fulfilment shortfalls cannot reduce later generated demand.
- Two drones start at the two banks. Each carries four packaged units, travels at 60 km/h and spends two minutes loading and two unloading. A complete reposition-and-delivery mission may take at most 40 minutes. The fleet and performance values are synthetic. Charging, battery degradation, real air corridors, permits, packaging and cold-chain validation are not modelled.
- Distance uses Haversine geometry between the supplied site coordinates. Road ETAs are not reused as flight times. A delivered drone remains at the receiving hospital; its next mission must include repositioning.
- Blocked delivery links cancel unlaunched deliveries and release their reservations. Repositioning drones finish repositioning before becoming free. Existing delivery flights continue: no midflight diversion or disruption hazard is simulated.
- Sunday stock arrivals are already-processed usable stock under a declared scenario event. They are not simulated donations made instantly usable. External X1 has no supported missions.
- Deadline misses are retained as unmet units, not silently converted to fulfilled demand. The simulator uses real elapsed timestamps and displays Europe/Paris offsets across Sunday's clock change.

## Verification and replay evidence

```powershell
python -m unittest discover -s tests -v
python -m blood_response validate
```

Tests cover shared unit reservations, in-transit availability, destination consumption, drone repositioning, alternative sources, expiry, stale plans, deadline boundaries, shortages, cancellation, API failures, the API's sole-plan boundary, HTTP validation and full-weekend source preservation. Ledger assertions run after operational events. The deterministic baseline uses identical incoming requests and social posts to the live run.

`api-receipts.jsonl` stores the actual API inputs, outputs, provider request IDs, latency and usage. `replay.json` stores chronological browser frames and summary counts. `final-state.json` stores the resulting unit ledger. Runs are ignored by Git. The original 16–18 October API results are untouched; these calls are a separate forward operational demonstration. Neither this simulation nor a successful model choice validates clinical allocation or real drone transport.
