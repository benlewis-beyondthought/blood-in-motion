# Blood in motion interface

The dispatch application now uses React, TypeScript, shadcn/ui's Base UI Nova components, Tailwind CSS, Geist and Leaflet. Warm neutral surfaces and one crimson accent keep the map, stock and requests easy to scan.

## Run the included build

From the repository root:

```sh
python -m pip install -r requirements.txt
python -m blood_response.dispatch_server --scheduler rolling --port 8879 --output runs/my-interface-demo
```

Open http://127.0.0.1:8879/. Use a new output directory for each server invocation. The built files are included, so Node.js is not needed to run the application. Map tiles need internet access. Fonts and the JavaScript application are bundled locally.

The Python simulation, canonical data, controller options, API routes and saved replay schema are unchanged. A rolling scheduler is deterministic. Use the existing `--scheduler greedy --controller decisions --prompt-key` options for model-selected feasible transfers; see [the dispatch guide](DRONE-DEMO.md). This interface work did not make new paid API calls.

## Controls

- **Play simulation**, **Pause**, **Next event** and the speed selector control the simulation clock.
- **New request** opens a labelled form. Enter hospital, blood group, units, deadline and priority. Confirmed requests go to the existing simulation API.
- **Requests / Social** separates operational demand from social evidence. Both remain visible alongside the map.
- **Decision insights** contains **Why this plan?** and **What would help?**. Alternative plans and shortage constraints open in dialogs.
- **Inventory** shows available and reserved stock. **Event log** shows operational history and API call counts.
- **Replay & tools** contains review, import, export and new-run actions. Recorded playback disables request injection and intervention computation. It makes no API calls.
- **Simulation assumptions** gives the scenario limits without crowding the operational view.

## Edit the interface

Use Node.js 24 and npm:

```sh
cd frontend
npm ci
npm run build
```

The build type-checks TypeScript and writes `index.html`, `app.js` and `style.css` into `blood_response/web/`. Refresh the Python-served page after building. `npm run dev` watches files and rebuilds into the same directory; it does not run a separate frontend server. Run `npm run build` before sharing changes to include the type check.

The static build keeps the existing server route contract. A single JavaScript bundle and embedded font assets avoid adding a second runtime server or extra asset endpoints. `__CSRF_TOKEN__` in the HTML remains a placeholder until the Python server supplies the session token. No credentials are built into frontend files.

Component source lives in `frontend/src/components/ui/`. Product layout and theme live in `frontend/src/index.css`; map rendering, analysis panels and simulation interaction are separate modules. CI now installs the locked frontend dependencies and runs the production build before Python validation.

The shadcn 4.22.1 CSS utilities are preserved in `frontend/src/vendor/shadcn.css`, with the upstream MIT license alongside them. The component CLI is not an installed app dependency. Frontend dependency notices, including the Geist font license, are retained in `frontend/THIRD_PARTY_NOTICES.txt`.

## Verification

The production build and strict TypeScript check pass. All 53 existing Python regression tests pass, including HTTP request validation, unit conservation, replay chronology and isolation of what-if calculations. Browser checks cover request submission, drone dispatch and receipt, inventory, social reports, replay seeking, disabled actions during replay, dialogs and keyboard dismissal. Desktop and 390/320-pixel layouts were inspected. These checks verify the interface and existing synthetic workflow, not clinical allocation or real drone transport.
