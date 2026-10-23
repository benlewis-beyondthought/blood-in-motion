from copy import deepcopy
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from blood_response.demo import build_demo, instant, prepare_handoffs, read_reports, write_demo
from blood_response.model import DEFAULT_DATA, ROOT


class ChronologicalDemoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source_files = [p for folder in [DEFAULT_DATA, ROOT / "paris-protest-social-simulation-v1", ROOT / "openai-decisions-replay-v1"] for p in folder.rglob("*") if p.is_file()]
        cls.hashes = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in cls.source_files}
        cls.demo = build_demo()

    def test_complete_flow_and_source_preservation(self):
        result = self.demo
        self.assertEqual(result["summary"]["frames"], 121)
        self.assertEqual(result["summary"]["reports_replayed"], 36)
        self.assertEqual(result["summary"]["reports_outside_horizon"], 0)
        self.assertEqual(result["summary"]["hourly_ticks"], 84)
        self.assertEqual(result["summary"]["conservation"], "PASS")
        self.assertEqual(result["summary"]["live_api_calls"], 0)
        self.assertEqual(result["summary"]["database_writes"], 0)
        self.assertEqual(result["summary"]["proposal_executions"], 0)
        self.assertEqual(result["assessment_origin"], "scripted_forward_reference_not_a_model_run")
        self.assertEqual(self.hashes, {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.source_files})

    def test_social_frames_do_not_inflate_inventory_or_demand(self):
        frames = self.demo["frames"]
        for earlier, current in zip(frames, frames[1:]):
            if current["kind"] == "social_report":
                self.assertEqual(current["inventory"], earlier["inventory"])
                self.assertEqual(current["plan"], earlier["plan"])
                self.assertIsNone(current["social_added_demand_units"])
        control = build_demo(include_social=False)
        self.assertEqual(control["summary"]["inventory_ledger_sha256"], self.demo["summary"]["inventory_ledger_sha256"])
        self.assertEqual(control["ticks"], self.demo["ticks"])

    def test_no_future_posts_or_inventory_in_any_frame(self):
        reports = {r["report_id"]: r for r in self.demo["reports"]}
        frames = self.demo["frames"]
        self.assertEqual([instant(f["at"]) for f in frames], sorted(instant(f["at"]) for f in frames))
        self.assertEqual(frames[0]["social"]["reports_seen"], 0)
        for frame in frames:
            self.assertLessEqual(instant(frame["inventory_as_of"]), instant(frame["at"]))
            self.assertEqual(frame["plan"]["as_of"], frame["inventory_as_of"])
            self.assertEqual(frame["social"]["reports_seen"], len(frame["social"]["seen_report_ids"]))
            for rid in frame["social"]["seen_report_ids"]:
                self.assertLessEqual(instant(reports[rid]["available_at"]), instant(frame["at"]))
            for event in frame["social"]["events"]:
                self.assertTrue(set(event["report_ids"]) <= set(frame["social"]["seen_report_ids"]))

    def test_clock_change_keeps_two_real_hours_and_report_offsets(self):
        clocks = [f["at"] for f in self.demo["frames"] if f["kind"] == "inventory_tick"]
        self.assertIn("2026-10-25T02:00:00+02:00", clocks)
        self.assertIn("2026-10-25T02:00:00+01:00", clocks)
        for a, b in zip(clocks, clocks[1:]):
            self.assertEqual(instant(b) - instant(a), timedelta(hours=1))
        sunday = [f for f in self.demo["frames"] if f["kind"] == "social_report" and f["at"].startswith("2026-10-25")]
        self.assertTrue(all(f["at"].endswith("+01:00") for f in sunday))

    def test_duplicate_suppression_and_foreign_event_routing_reach_screen_state(self):
        by_id = {f["report_id"]: f for f in self.demo["frames"] if f["report_id"]}
        duplicate = by_id["SOC-018"]["social"]["handoff"]
        self.assertEqual(duplicate["paris_action"], "IGNORE")
        self.assertEqual(duplicate["event_review_priority"], "URGENT_REVIEW")
        lyon = by_id["SOC-015"]["social"]
        self.assertEqual(lyon["handoff"]["paris_action"], "IGNORE")
        event = next(e for e in lyon["events"] if e["event_id"] == lyon["handoff"]["event_id"])
        self.assertEqual(event["candidate_site_ids"], [])
        self.assertEqual(event["route"], "regional_or_unlocated_context")

    def test_shared_proposals_are_nonexecuting_and_known_route_only(self):
        for frame in self.demo["frames"]:
            ids = [uid for proposal in frame["plan"]["transfer_proposals"] for uid in proposal["unit_ids"]]
            self.assertEqual(len(ids), len(set(ids)))
            self.assertEqual(frame["proposal_execution"], "not_executed")
            self.assertFalse(any(p["from_site_id"] == "X1" for p in frame["plan"]["transfer_proposals"]))
        initial = self.demo["frames"][0]
        self.assertEqual(initial["inventory"]["available_units"], 777)
        self.assertEqual(sum(p["units"] for p in initial["plan"]["transfer_proposals"]), 15)

    def test_recorded_historical_api_outputs_are_rejected_for_forward_demo(self):
        historical = ROOT / "openai-decisions-replay-v1" / "baseline" / "predictions.json"
        with self.assertRaisesRegex(ValueError, "clock mismatch"):
            prepare_handoffs(DEFAULT_DATA, read_reports(DEFAULT_DATA), historical)

    def test_export_is_self_contained_escapes_posts_and_preserves_existing_runs(self):
        fake = {"reports": [{"text": '</script><img src=x onerror="alert(1)">'}], "summary": {"live_api_calls": 0}}
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "demo"
            with patch("blood_response.demo.build_demo", return_value=fake):
                write_demo(output)
            html = (output / "index.html").read_text(encoding="utf-8")
            self.assertIn("\\u003c/script>", html)
            self.assertNotIn('<img src=x', html)
            self.assertNotIn("__DEMO_JSON__", html)
            self.assertEqual(json.loads((output / "demo.json").read_text(encoding="utf-8")), fake)
            with self.assertRaises(FileExistsError):
                write_demo(output)


if __name__ == "__main__":
    unittest.main()
