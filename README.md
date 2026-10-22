# Paris blood-service social simulation

A small hackathon dataset and chronological replay using OpenAI's Decisions API. The social component flags reports that could matter to blood-service planning. Patient requirements and blood storage belong to separate datasets.

**All 36 social posts, accounts, exact posting times, local injury claims, and blood-service consequences are synthetic.** Real reporting informed the setting for 16–18 October 2026. This is not a reconstruction of verified casualties, a record of real blood shortages, or a clinical system.

## Start here

- [Synthetic Friday–Sunday timeline](paris-protest-social-simulation-v1/TIMELINE.md)
- [What the live API run showed](openai-decisions-replay-v1/FINDINGS.md)
- [Every incoming post: expected and actual flags](openai-decisions-replay-v1/COMPARISON.md)
- [Decision rubric](paris-protest-social-simulation-v1/decision_rubric.json)
- [Research sources and limits](paris-protest-social-simulation-v1/RESEARCH.md)

## Recorded result

One chronological trajectory: 36 posts, three requests per post, 108 successful Decisions API requests using `gpt-6-luna`.

| Comparison | Agreement with the authored reference |
|---|---:|
| Report action flag | 32/36 (88.9%) |
| Event priority after each linked post | 22/33 (66.7%) |
| New information / duplicate / correction classification | 27/36 (75.0%) |

The expected labels were assistant-authored and have not been independently reviewed. These are agreement figures, not clinical accuracy. The [findings](openai-decisions-replay-v1/FINDINGS.md) explain ambiguous labels and inconsistencies exposed by the run. No expected labels or future reports were included in the inference evidence.

The run consumed 392,724 input tokens. At the documented base rate, the input-cost estimate was about USD 0.04; this is not a billing receipt.

## Run locally

Python 3.12 was used. The scripts use only the Python standard library.

```sh
git clone https://github.com/benlewis-beyondthought/paris-blood-social-simulation.git
cd paris-blood-social-simulation
python paris-protest-social-simulation-v1/validate_dataset.py
python run_decisions_replay.py --self-test
```

To make a fresh live run:

```sh
python run_decisions_replay.py --run-dir runs/my-replay
```

Provide your own OpenAI API key at the hidden prompt, or set `OPENAI_API_KEY` in your process environment. The runner does not automatically load `.env` files. No key is included in this repository. Live runs use the direct Decisions API and can incur charges. They do not change the frozen baseline included here.

The new run writes a chronological `COMPARISON.md`, machine-readable scores, model-built event histories, and request/response receipts under the chosen run directory. A cached run can resume only when its dataset, rubric, runner and model fingerprints match.

## Repository contents

```text
run_decisions_replay.py                  # Live replay and comparison runner
paris-protest-social-simulation-v1/      # Inputs, expected labels, rubric, source notes
openai-decisions-replay-v1/              # Frozen observed baseline and findings
  baseline/calls/                       # API requests and responses; no auth headers
  baseline/traces/                      # Per-post evidence and output traces
```

The generated `report.html` can be downloaded and opened locally. GitHub's file view does not run the report's HTML. The Markdown comparison works directly in GitHub.

## Scope and next steps

This component emits event locations, evidence assessments and review priorities. It does not predict transfusion units, assign patients to hospitals, or read actual blood inventories. Keep the baseline frozen while reviewing event grouping, timing ambiguity, source geography, and the distinction between lifecycle and evidence status.

The next implementation step is to enforce duplicate suppression and consistent escalation in ordinary code, then compare a separately named version with this baseline. The current recorded run leaves those decisions to the model so their inconsistencies remain visible.
