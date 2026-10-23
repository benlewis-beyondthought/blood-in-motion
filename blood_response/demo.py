"""Offline chronological application flow using the merged canonical contract.

Scripted reference decisions exercise the application by default. They are not
inference, an evaluation result, or re-dated historical API responses.
"""
from collections import Counter
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from .model import DEFAULT_DATA, advance, load_world, plan, validate
from .social import normalize, PRIORITY


def instant(value):
    when = datetime.fromisoformat(value)
    if when.utcoffset() is None:
        raise ValueError("Demo timestamps must include a timezone offset")
    return when.astimezone(timezone.utc)


def read_reports(folder):
    reports = [json.loads(line) for line in (Path(folder) / "social_reports.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    ids = [r["report_id"] for r in reports]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate social report ID")
    if reports != sorted(reports, key=lambda r: instant(r["available_at"])):
        raise ValueError("Social reports must be chronological")
    for report in reports:
        if instant(report["published_at"]) > instant(report["available_at"]):
            raise ValueError("Report available before publication")
    return reports


def scripted_predictions(folder, reports):
    """Explicit scenario script, including authored event grouping. No API calls."""
    reference = [json.loads(line) for line in (Path(folder) / "expected_decisions.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    by_id = {r["report_id"]: r for r in reference}
    if len(by_id) != len(reference) or set(by_id) != {r["report_id"] for r in reports}:
        raise ValueError("Scripted reference IDs do not match reports")
    output = []
    for report in reports:
        ref = by_id[report["report_id"]]
        assessment = dict(ref["decisions"])
        assessment["reported_impact_level_mode"] = assessment["reported_impact_level"]
        output.append({"report_id": report["report_id"], "available_at": report["available_at"],
            "assessment": assessment, "event_id": ref["comparison"]["expected_event_id"],
            "decisions": {"contribution": ref["comparison"]["contribution"]},
            "origin": "scripted_reference_for_application_demo_not_inference"})
    return output


def prepare_handoffs(folder, reports, predictions_path=None):
    if predictions_path is None:
        predictions = scripted_predictions(folder, reports)
        origin = "scripted_forward_reference_not_a_model_run"
    else:
        predictions = json.loads(Path(predictions_path).read_text(encoding="utf-8"))
        origin = "supplied_aligned_predictions_not_independently_authenticated"
    ids = [p["report_id"] for p in predictions]
    if ids != [r["report_id"] for r in reports]:
        raise ValueError("Predictions must cover each report once, in the same order")
    # The shared policy checks exact report/prediction timestamps. In particular,
    # the frozen historical outputs cannot be used as forward-scenario inference.
    handoffs = normalize(reports, predictions)
    for row in handoffs:
        row["origin"] = "deterministic_application_policy"
        row["assessment_origin"] = origin
    return handoffs, origin


def inventory_summary(world):
    today = datetime.fromisoformat(world["clock"]).date().isoformat()
    counts = Counter((u["site_id"], u["blood_type"]) for u in world["units"]
        if u["status"] == "available" and u["expiry_date"] > today)
    rows = [{"site_id": s["site_id"], "blood_type": blood, "available_units": counts[(s["site_id"], blood)]}
            for s in world["sites"] for blood in world["scenario"]["blood_types"]]
    return {"as_of": world["clock"], "available_units": sum(counts.values()), "rows": rows}


def planning_snapshot(world):
    result = plan(world)
    units = [uid for proposal in result["transfer_proposals"] for uid in proposal["unit_ids"]]
    if len(units) != len(set(units)):
        raise AssertionError("A unit was proposed more than once")
    return result


def build_demo(folder=DEFAULT_DATA, *, hours=84, seed=42, predictions_path=None, include_social=True):
    if not isinstance(hours, int) or hours < 1:
        raise ValueError("Demo hours must be a positive integer")
    world = load_world(folder)
    validate(world)
    start = instant(world["clock"])
    finish = start + timedelta(hours=hours)
    # Validate the entire requested planning horizon before simulating anything.
    if (finish.astimezone(ZoneInfo(world["scenario"]["timezone"])).date() + timedelta(days=1)).isoformat() > world["scenario"]["known_planning_end"]:
        raise ValueError("Demo horizon exceeds supplied next-day planning coverage")
    reports = read_reports(folder) if include_social else []
    if any(instant(r["available_at"]) < start for r in reports):
        raise ValueError("Social reports predate the inventory snapshot")
    handoffs, origin = prepare_handoffs(folder, reports, predictions_path) if reports else ([], "social_disabled_control")
    by_id = {r["report_id"]: r for r in reports}
    context = json.loads((Path(folder) / "social_site_context.json").read_text(encoding="utf-8"))
    schedule = [(start + timedelta(hours=i), 0, "inventory_tick", i) for i in range(1, hours + 1)]
    schedule.extend((instant(row["available_at"]), 1, "social_report", row) for row in handoffs if instant(row["available_at"]) <= finish)
    schedule.sort(key=lambda entry: (entry[0], entry[1]))
    frames, events, seen, ticks = [], {}, [], []
    inventory = inventory_summary(world)
    planning = planning_snapshot(world)

    def capture(at, kind, report_id=None, tick=None, handoff=None):
        frames.append({"frame": len(frames), "at": at, "kind": kind, "report_id": report_id,
            "inventory_as_of": world["clock"], "inventory": deepcopy(inventory), "plan": deepcopy(planning),
            "social": {"reports_seen": len(seen), "seen_report_ids": list(seen), "handoff": deepcopy(handoff),
                "events": sorted(deepcopy(list(events.values())), key=lambda e: (-PRIORITY[e["review_priority"]], e["event_id"]))},
            "tick": deepcopy(tick), "social_added_demand_units": None, "proposal_execution": "not_executed"})

    capture(world["clock"], "initial_snapshot")
    for _, _, kind, item in schedule:
        if kind == "inventory_tick":
            tick = advance(world, seed=seed)
            validate(world)
            ticks.append(tick)
            inventory = inventory_summary(world)
            planning = planning_snapshot(world)
            capture(world["clock"], kind, tick=tick)
            continue
        row = item
        report = by_id[row["report_id"]]
        seen.append(report["report_id"])
        event_id = row["event_id"]
        if event_id:
            event = events.setdefault(event_id, {"event_id": event_id, "report_ids": [], "zone": "unknown"})
            event["report_ids"].append(report["report_id"])
            if row["zone"] != "unknown":
                event["zone"] = row["zone"]
            event.update(review_priority=row["event_review_priority"], event_phase=row["event_phase"],
                evidence_status=row["evidence_status"], last_report_id=report["report_id"],
                last_report_at=report["available_at"])
            event["candidate_site_ids"] = context["demo_zone_candidates"].get(event["zone"], [])
            event["candidate_mapping_basis"] = context["mapping_status"]
            event["route"] = "paris_review" if event["zone"].startswith("paris_") else "regional_or_unlocated_context"
        # No changes to world, forecasts or stock are permitted on a social step.
        capture(report["available_at"], kind, report_id=report["report_id"], handoff=row)
    final = validate(world)
    return {"schema_version": "1.0", "title": "Paris response replay", "is_synthetic": True,
        "scenario_id": world["scenario"]["dataset_id"], "timezone": world["scenario"]["timezone"],
        "assessment_origin": origin, "seed": seed, "hours": hours, "start": frames[0]["at"], "end": world["clock"],
        "sites": world["sites"], "blood_types": world["scenario"]["blood_types"], "reports": reports,
        "frames": frames, "ticks": ticks, "social_site_context": context,
        "summary": {"frames": len(frames), "reports_replayed": len(seen), "reports_outside_horizon": len(reports) - len(seen),
            "hourly_ticks": len(ticks), "final_validation": final, "conservation": "PASS",
            "requested": sum(t["requested"] for t in ticks), "used": sum(t["used"] for t in ticks),
            "unmet_simulated_requests": sum(t["unmet_requests"] for t in ticks),
            "inventory_ledger_sha256": hashlib.sha256(json.dumps(world, sort_keys=True).encode()).hexdigest(),
            "live_api_calls": 0, "database_writes": 0, "proposal_executions": 0},
        "limits": ["All counts, demand rules, travel estimates and social posts are synthetic or unverified demo assumptions.",
            "Forward social decisions are scripted by default. Recorded API agreement scores concern the original 16–18 October replay only.",
            "Social evidence triggers investigation; it does not add transfusion units, assign patients or alter stock.",
            "Candidate facilities use a coarse demo mapping, not a verified catchment. Fictional institutions are not real site identities.",
            "Stock advances hourly; report time and latest inventory time are displayed separately.",
            "The planner considers the next full day. Proposed units are not reserved or dispatched.",
            "Proposals are recalculated for each snapshot. Proposals from different frames are alternatives, not cumulative commitments.",
            "The seeded simulator independently consumes units, creates immediate-use synthetic donations and logs replenishment. These are simulated ledger movements, not executed proposals.",
            "External supplier ETAs remain unknown and cannot justify new proposals."]}


def write_demo(output, folder=DEFAULT_DATA, **options):
    output = Path(output)
    if output.exists():
        raise FileExistsError("Choose a new demo output directory; existing runs are preserved: " + str(output))
    demo = build_demo(folder, **options)
    template = (Path(__file__).parent / "demo.html").read_text(encoding="utf-8")
    # JSON inside an inert data element still needs '<' escaped to prevent an
    # untrusted post from ending the script element. UI text uses textContent.
    data = json.dumps(demo, ensure_ascii=False).replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    output.mkdir(parents=True, exist_ok=False)
    (output / "demo.json").write_text(json.dumps(demo, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "index.html").write_text(template.replace("__DEMO_JSON__", data), encoding="utf-8")
    (output / "README.txt").write_text("Open index.html in a browser. It works offline. Select Next report to replay the 36 hypothetical forward posts alongside the hourly stock simulation.\n\nSocial decisions are scripted references, not a new API run. Social reports do not add blood-demand units. Proposals remain unexecuted. The complete data and provenance are in demo.json.\n", encoding="utf-8")
    return {"output": str(output), **demo["summary"]}
