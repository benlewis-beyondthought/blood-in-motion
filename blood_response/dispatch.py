"""Event-driven, synthetic drone distribution. Canonical inputs remain read-only."""
from collections import Counter
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import heapq
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo
from . import model
from .decisions import Controller

ZONE = ZoneInfo("Europe/Paris")
PRIORITY = {"critical": 0, "scheduled": 1, "routine": 2}


def stamp(value):
    return datetime.fromisoformat(value).timestamp() if isinstance(value, str) else float(value)


def iso(value):
    return datetime.fromtimestamp(value, ZONE).isoformat()


def km(a, b):
    a1, b1 = math.radians(float(a["lat"])), math.radians(float(b["lat"]))
    h = math.sin((b1-a1)/2)**2 + math.cos(a1)*math.cos(b1)*math.sin(math.radians(float(b["lon"])-float(a["lon"]))/2)**2
    return 12742 * math.asin(min(1, math.sqrt(h)))


class Simulation:
    def __init__(self, data=model.DEFAULT_DATA, controller=None, scripted=True, scheduler='greedy'):
        if scheduler not in {'greedy', 'rolling'}:
            raise ValueError('Unknown scheduler')
        self.scheduler, self.analysis = scheduler, False
        self.diagnostics, self.planning = [], None
        self.checkpoints, self.experiments = {}, {}
        world = model.load_world(data)
        model.validate(world)
        self.controller = controller or Controller()
        self.api_start = (self.controller.client.calls, self.controller.client.successes) if self.controller.client else (0, 0)
        self.sites = {s["site_id"]: deepcopy(s) for s in world["sites"] if s["site_type"] != "external"}
        self.units = {u["unit_id"]: deepcopy(u) for u in world["units"]}
        self.groups = world["scenario"]["blood_types"]
        self.baseline = model.baselines(world)  # Freeze observed baseline; simulated use does not train demand.
        self.planned = world["planned_activity"]
        self.now = stamp(world["clock"])
        self.end = stamp("2026-10-26T00:00:00+01:00")
        self.initial_units = len(self.units)
        self.received_units = 0
        self.initial_used = sum(u["status"] == "used" for u in self.units.values())
        self.requests, self.missions, self.reports, self.decisions, self.log = [], [], [], [], []
        self.queue, self.sequence, self.version = [], 0, 0
        self.blocked = set()
        self.drone_config = {"payload_units": 4, "speed_kmh": 60, "load_minutes": 2,
                             "unload_minutes": 2, "max_mission_minutes": 40}
        self.drones = {"D1": {"drone_id": "D1", "site_id": "B1", "status": "idle", "mission_id": None},
                       "D2": {"drone_id": "D2", "site_id": "B2", "status": "idle", "mission_id": None}}
        if scripted:
            self.seed_events(Path(data))
        self.frames = []
        self.record("START", "Inventory loaded · 777 available units · two simulated drones")
        self.capture()

    def enqueue(self, when, kind, payload):
        when = stamp(when)
        if when < self.now:
            raise ValueError("Cannot enqueue an event in the past")
        self.sequence += 1
        heapq.heappush(self.queue, (when, self.sequence, kind, deepcopy(payload)))

    def seed_events(self, data):
        # The fixture has date-only procedures. 09:00 release and noon deadline are explicit assumptions.
        for day in ["2026-10-23", "2026-10-24", "2026-10-25"]:
            start = datetime.fromisoformat(day).replace(tzinfo=ZONE)
            planned, critical = Counter(), Counter()
            for p in self.planned:
                if p["date"] == day:
                    key = (p["site_id"], p["blood_type"])
                    planned[key] += int(p["units_expected"])
                    if p["priority"] == "scheduled_critical":
                        critical[key] += int(p["units_expected"])
            for site, s in self.sites.items():
                if s["site_type"] != "hospital":
                    continue
                for blood in self.groups:
                    key = (site, blood)
                    scheduled = planned[key]
                    extra = max(0, math.ceil(self.baseline.get(key, 0)) - scheduled)
                    for label, amount, hour, priority in [("planned", scheduled, 9, "critical" if critical[key] else "scheduled"),
                                                          ("background", extra, 15, "routine")]:
                        if amount:
                            at = (start + timedelta(hours=hour)).timestamp()
                            self.enqueue(at, "request", {"site_id": site, "blood_type": blood, "units": amount,
                                "deadline": iso(at + 3*3600), "priority": priority, "source": label,
                                "note": "Date-only planned demand" if label == "planned" else "Residual baseline; avoids double counting planned activity"})
            self.enqueue(start.timestamp(), "expiry", {})
        for line in (data / "social_reports.jsonl").read_text(encoding="utf-8").splitlines():
            if line.strip():
                report = json.loads(line)
                self.enqueue(report["available_at"], "social", report)
        self.enqueue("2026-10-23T10:05:00+02:00", "request", {
            "site_id": "H1", "blood_type": "O-", "units": 8, "deadline": "2026-10-23T10:50:00+02:00",
            "priority": "critical", "source": "scenario_emergency", "note": "Invented additional hospital request"})
        self.enqueue("2026-10-24T11:55:00+02:00", "route", {"from": "B2", "to": "H4", "blocked": True})
        self.enqueue("2026-10-24T12:07:00+02:00", "request", {
            "site_id": "H4", "blood_type": "A+", "units": 16, "deadline": "2026-10-24T13:07:00+02:00",
            "priority": "critical", "source": "scenario_emergency", "note": "Independent hospital confirmation; not inferred from social posts"})
        self.enqueue("2026-10-24T12:09:00+02:00", "request", {
            "site_id": "H1", "blood_type": "O-", "units": 40, "deadline": "2026-10-24T12:24:00+02:00",
            "priority": "critical", "source": "scenario_stress", "note": "Deliberate shortage challenge; impossible full fulfilment is allowed"})
        self.enqueue("2026-10-24T13:15:00+02:00", "route", {"from": "B2", "to": "H4", "blocked": False})
        self.enqueue("2026-10-25T10:00:00+01:00", "receipt", {"site_id": "B1", "blood_type": "O-", "units": 12})
        self.enqueue(self.end, "expiry", {})
        self.enqueue(self.end, "end", {})

    def record(self, kind, message, **data):
        self.log.append({"at": iso(self.now), "kind": kind, "message": message, **data})

    def available(self, site, blood, when=None):
        day = iso(self.now if when is None else when)[:10]
        if self.analysis:
            if getattr(self, '_available_index', None) is None:
                self._available_index = {}
                for unit in self.units.values():
                    if unit['status'] == 'available':
                        self._available_index.setdefault((unit['site_id'], unit['blood_type']), []).append(unit)
                for units in self._available_index.values():
                    units.sort(key=lambda u: (u['expiry_date'], u['unit_id']))
            return [u for u in self._available_index.get((site, blood), []) if u['expiry_date'] > day]
        return sorted([u for u in self.units.values() if u["status"] == "available" and
                       u["site_id"] == site and u["blood_type"] == blood and u["expiry_date"] > day],
                      key=lambda u: (u["expiry_date"], u["unit_id"]))

    def reserve(self, site, blood):
        s = self.sites[site]
        if s["site_type"] == "blood_bank":
            return math.ceil(sum(self.baseline.get((h, blood), 0) for h, v in self.sites.items() if v.get("home_bank_id") == site))
        planned = sum(int(p["units_expected"]) for p in self.planned if p["site_id"] == site and
                      p["blood_type"] == blood and p["date"] == iso(self.now)[:10])
        waiting = sum(r["units"]-r["fulfilled"] for r in self.requests if r["site_id"] == site and
                      r["blood_type"] == blood and r["status"] == "waiting")
        return max(math.ceil(self.baseline.get((site, blood), 0)), planned, waiting)

    def pending(self):
        return sorted([r for r in self.requests if r["status"] == "waiting"],
                      key=lambda r: (PRIORITY[r["priority"]], stamp(r["deadline"]), r["request_id"]))

    def committed(self, request):
        return sum(len(m["unit_ids"]) for m in self.missions if m["request_id"] == request["request_id"] and m["status"] in {"repositioning", "loading", "flying", "unloading"})

    def consume(self, request, units):
        if units:
            self._available_index = None
        for u in units:
            assert u["status"] == "available" and u["site_id"] == request["site_id"]
            u.update(status="used", used_date=iso(self.now)[:10], request_id=request["request_id"])
            request["fulfilled"] += 1
            request["fulfilled_unit_ids"].append(u["unit_id"])
        if request["fulfilled"] == request["units"]:
            request.update(status="fulfilled", fulfilled_at=iso(self.now))

    def plans(self, request):
        remaining = request["units"]-request["fulfilled"]-self.committed(request)
        if remaining <= 0:
            return []
        target, blood, cfg = request["site_id"], request["blood_type"], self.drone_config
        plans = []
        for source in self.sites:
            if source == target or (source, target) in self.blocked:
                continue
            for drone in self.drones.values():
                if drone["status"] != "idle":
                    continue
                if drone["site_id"] != source and (drone["site_id"], source) in self.blocked:
                    continue
                reposition = km(self.sites[drone["site_id"]], self.sites[source])
                delivery = km(self.sites[source], self.sites[target])
                minutes = (reposition + delivery) / cfg["speed_kmh"] * 60 + cfg["load_minutes"] + cfg["unload_minutes"]
                arrival = self.now + math.ceil(minutes*60)
                if minutes > cfg["max_mission_minutes"] or arrival > stamp(request["deadline"]):
                    continue
                stock = self.available(source, blood, arrival)
                count = min(remaining, cfg["payload_units"], max(0, len(stock)-self.reserve(source, blood)))
                if count:
                    plans.append({"plan_id": f"P-{self.version}-{source}-{drone['drone_id']}",
                        "version": self.version, "request_id": request["request_id"], "drone_id": drone["drone_id"],
                        "from_site_id": source, "to_site_id": target, "blood_type": blood,
                        "units": count, "unit_ids": [u["unit_id"] for u in stock[:count]],
                        "drone_start_site": drone["site_id"], "reposition_km": round(reposition, 6),
                        "delivery_km": round(delivery, 6), "arrival_at": iso(arrival),
                        "source_reserve": self.reserve(source, blood)})
        return sorted(plans, key=lambda p: (-p["units"], stamp(p["arrival_at"]), p["reposition_km"]+p["delivery_km"], p["plan_id"]))

    def dispatch(self, plan, decision):
        request = next(r for r in self.requests if r["request_id"] == plan["request_id"])
        current = self.plans(request) if request["status"] == "waiting" else []
        if plan not in current:
            raise ValueError("Stale or infeasible plan rejected")
        mission = deepcopy(plan)
        mission["mission_id"] = f"M-{len(self.missions)+1:04d}"
        mission["decision_id"] = decision["decision_id"]
        mission["reserved_at"] = iso(self.now)
        load_start = self.now + math.ceil(plan["reposition_km"] / self.drone_config["speed_kmh"] * 3600)
        mission["load_at"] = iso(load_start)
        mission["depart_at"] = iso(load_start + self.drone_config["load_minutes"]*60)
        mission["land_at"] = iso(stamp(plan["arrival_at"])-self.drone_config["unload_minutes"]*60)
        mission["status"] = "repositioning" if plan["reposition_km"] else "loading"
        for uid in plan["unit_ids"]:
            self.units[uid].update(status="reserved", mission_id=mission["mission_id"])
        self._available_index = None
        self.drones[plan["drone_id"]].update(status=mission["status"], mission_id=mission["mission_id"])
        self.missions.append(mission)
        for at, kind in [(mission["load_at"], "load"), (mission["depart_at"], "depart"),
                         (mission["land_at"], "land"), (mission["arrival_at"], "arrive")]:
            self.enqueue(at, kind, {"mission_id": mission["mission_id"]})
        self.version += 1
        self.record("DISPATCH", f"{mission['drone_id']} reserved {plan['units']} {plan['blood_type']} · {plan['from_site_id']} → {plan['to_site_id']}", mission_id=mission["mission_id"])

    def allocate(self):
        if self.scheduler == 'rolling':
            self.allocate_rolling()
        else:
            self.allocate_greedy()
        if not self.analysis:
            self.update_diagnostics()

    def update_diagnostics(self):
        from .planning import diagnose, fork_known
        current = []
        for request in self.pending():
            if request['units']-request['fulfilled']-self.committed(request) <= 0:
                continue
            item = diagnose(self, request)
            request['diagnostic'] = item
            current.append(item)
            if request['request_id'] not in self.checkpoints:
                self.checkpoints[request['request_id']] = fork_known(self, stamp(request['deadline']))
        self.diagnostics = current + [r['diagnostic'] for r in self.requests if r['status'] == 'missed' and 'diagnostic' in r]

    def what_helps(self, request_id):
        from .planning import what_helps
        if request_id not in self.checkpoints:
            raise ValueError('No unresolved snapshot for this request')
        if request_id not in self.experiments:
            self.experiments[request_id] = what_helps(self.checkpoints[request_id], request_id)
        return deepcopy(self.experiments[request_id])

    def allocate_rolling(self):
        from .planning import choose
        for request in self.pending():
            needed = max(0, request['units']-request['fulfilled']-self.committed(request))
            self.consume(request, self.available(request['site_id'], request['blood_type'])[:needed])
        while any(d['status'] == 'idle' for d in self.drones.values()):
            selected, summary = choose(self)
            if selected is None:
                break
            self.planning = summary
            decision = {'decision_id': f'DEC-{len(self.decisions)+1:04d}', 'at': iso(self.now),
                        'request_id': selected['request_id'], 'selected_plan_id': selected['plan_id'],
                        'candidates': [selected], 'origin': 'rolling_horizon', 'planning': summary,
                        'reason': 'Best tested 90-minute continuation by priority fulfilment, then flight distance; no global optimality claim.'}
            self.dispatch(selected, decision)
            self.decisions.append(decision)
        for request in self.pending():
            request['waiting_reason'] = 'Delivery committed' if self.committed(request) >= request['units']-request['fulfilled'] else 'See shortage diagnostics and isolated what-if comparisons'

    def allocate_greedy(self):
        for request in self.pending():
            needed = max(0, request["units"]-request["fulfilled"]-self.committed(request))
            self.consume(request, self.available(request["site_id"], request["blood_type"])[:needed])
            while request["status"] == "waiting":
                plans = self.plans(request)
                if not plans:
                    request["waiting_reason"] = "Delivery committed" if self.committed(request) >= request["units"]-request["fulfilled"] else "Awaiting eligible stock or a drone that can meet the deadline"
                    break
                context = {"as_of": iso(self.now), "state_version": self.version, "request": request,
                           "other_pending_requests": self.pending(), "social_review_flags": [{"report_id": r["report_id"], "flag": r["flag"], "evidence": r["evidence"]} for r in self.reports[-6:]],
                           "policy": "Synthetic exact-group RBC allocation; protect declared reserves; no social-to-units conversion"}
                selected, meta = self.controller.select(context, plans)
                decision = {"decision_id": f"DEC-{len(self.decisions)+1:04d}", "at": iso(self.now),
                            "request_id": request["request_id"], "selected_plan_id": selected["plan_id"],
                            "candidates": plans, **meta}
                self.dispatch(selected, decision)
                self.decisions.append(decision)

    def add_request(self, data):
        site, blood = data.get("site_id"), data.get("blood_type")
        count, priority = data.get("units"), data.get("priority", "critical")
        if site not in self.sites or self.sites[site]["site_type"] != "hospital" or blood not in self.groups:
            raise ValueError("Select a known hospital and blood group")
        if type(count) is not int or not 1 <= count <= 100 or priority not in PRIORITY:
            raise ValueError("Units must be an integer from 1 to 100 and priority must be valid")
        deadline = stamp(data["deadline"])
        if deadline <= self.now or deadline > self.end:
            raise ValueError("Deadline must be after now and within the scenario")
        request = {"request_id": f"R-{len(self.requests)+1:04d}", "site_id": site, "blood_type": blood,
                   "units": count, "deadline": iso(deadline), "priority": priority, "source": str(data.get("source", "manual"))[:80],
                   "note": str(data.get("note", ""))[:500], "created_at": iso(self.now), "fulfilled": 0,
                   "fulfilled_unit_ids": [], "status": "waiting"}
        self.requests.append(request)
        self.enqueue(deadline, "deadline", {"request_id": request["request_id"]})
        self.record("REQUEST", f"{site} requests {count} {blood} · {priority}", request_id=request["request_id"])
        return request

    def process(self, kind, payload):
        self._available_index = None
        self.version += 1
        if kind == "request":
            self.add_request(payload)
        elif kind in {"load", "depart", "land", "arrive"}:
            m = next(m for m in self.missions if m["mission_id"] == payload["mission_id"])
            if m["status"] == "cancelled":
                return
            drone = self.drones[m["drone_id"]]
            status = {"load": "loading", "depart": "flying", "land": "unloading", "arrive": "delivered"}[kind]
            m["status"], drone["status"] = status, status
            if kind == "load":
                drone["site_id"] = m["from_site_id"]
            if kind == "depart":
                for uid in m["unit_ids"]:
                    self.units[uid].update(status="in_transit", site_id=None)
            if kind in {"land", "arrive"}:
                drone["site_id"] = m["to_site_id"]
            if kind == "arrive":
                for uid in m["unit_ids"]:
                    self.units[uid].update(status="available", site_id=m["to_site_id"])
                    self.units[uid].pop("mission_id", None)
                drone.update(status="idle", mission_id=None)
                request = next(r for r in self.requests if r["request_id"] == m["request_id"])
                if request["status"] == "waiting" and self.now <= stamp(request["deadline"]):
                    self.consume(request, [self.units[uid] for uid in m["unit_ids"]][:request["units"]-request["fulfilled"]])
                self.record("ARRIVAL", f"{m['drone_id']} delivered {m['units']} {m['blood_type']} to {m['to_site_id']}", mission_id=m["mission_id"])
        elif kind == "deadline":
            r = next(r for r in self.requests if r["request_id"] == payload["request_id"])
            # Arrivals at this exact instant are processed before deadline checks in step().
            if r["status"] == "waiting":
                r["status"] = "missed"
                self.record("SHORTAGE", f"{r['site_id']} deadline missed · {r['units']-r['fulfilled']} {r['blood_type']} units unmet", request_id=r["request_id"])
        elif kind == "social":
            assessment = self.controller.social(payload, self.reports)
            self.reports.append({**payload, **assessment, "blood_demand_increment": None})
            self.record("SOCIAL", f"{payload['report_id']} · {assessment['flag']}", report_id=payload["report_id"])
        elif kind == "route":
            pair = (payload["from"], payload["to"])
            if payload["blocked"]:
                self.blocked.add(pair)
                # Existing airborne missions continue under the declared no-midflight-diversion assumption.
                for m in self.missions:
                    if m["status"] in {"loading", "repositioning"} and (m["from_site_id"], m["to_site_id"]) == pair:
                        for uid in m["unit_ids"]:
                            self.units[uid].update(status="available")
                            self.units[uid].pop("mission_id", None)
                        d = self.drones[m["drone_id"]]
                        # Repositioning drone reaches source before becoming available; no teleport.
                        d.update(status="repositioning", mission_id=m["mission_id"])
                        self.enqueue(max(self.now, stamp(m["load_at"])), "release_drone", {"drone_id": d["drone_id"], "site_id": m["from_site_id"]})
                        m["status"] = "cancelled"
            else:
                self.blocked.discard(pair)
            self.record("ROUTE", f"Simulated flight link {pair[0]} → {pair[1]} {'unavailable' if payload['blocked'] else 'restored'}")
        elif kind == "release_drone":
            self.drones[payload["drone_id"]].update(site_id=payload["site_id"], status="idle", mission_id=None)
        elif kind == "receipt":
            self.received_units += payload["units"]
            for i in range(payload["units"]):
                uid = f"ARRIVAL-{len(self.units)+1}"
                self.units[uid] = {"unit_id": uid, "site_id": payload["site_id"], "blood_type": payload["blood_type"],
                    "component": "RBC", "status": "available", "expiry_date": "2026-11-25", "is_synthetic": "true"}
            self.record("STOCK", f"Scenario receipt · {payload['units']} {payload['blood_type']} at {payload['site_id']}")
        elif kind == "expiry":
            for u in self.units.values():
                if u["status"] == "available" and u["expiry_date"] <= iso(self.now)[:10]:
                    u["status"] = "expired"
        elif kind == "end":
            self.record("END", "Weekend scenario complete")

    def step(self, until=None):
        if not self.queue:
            return None if self.analysis else self.snapshot()
        next_time = self.queue[0][0]
        if until is not None and next_time > until:
            self.now = min(until, self.end)
            self.capture()
            return None if self.analysis else self.snapshot()
        self.now = next_time
        batch = []
        while self.queue and self.queue[0][0] == next_time:
            batch.append(heapq.heappop(self.queue))
        # Replenishment first, deadlines last. Allocate only after simultaneous requests are visible.
        order = {"arrive": 0, "receipt": 0, "expiry": 1, "route": 2, "deadline": 9, "end": 10}
        for _, seq, kind, payload in sorted(batch, key=lambda e: (order.get(e[2], 3), e[1])):
            self.process(kind, payload)
        self.allocate()
        self.check()
        self.capture()
        return None if self.analysis else self.snapshot()

    def tick(self):
        active = any(d["status"] != "idle" for d in self.drones.values())
        return self.step(until=self.now+60 if active else None)

    def inject(self, payload):
        if self.now >= self.end:
            raise ValueError("Scenario complete; start a new run")
        self.version += 1
        r = self.add_request(payload)
        self.allocate()
        self.check()
        self.capture()
        return r

    def check(self):
        assert len(self.units) == self.initial_units + self.received_units, "Inventory conservation failed"
        active_ids = []
        for m in self.missions:
            if m["status"] in {"repositioning", "loading", "flying", "unloading"}:
                active_ids.extend(m["unit_ids"])
                for uid in m["unit_ids"]:
                    u = self.units[uid]
                    assert u["mission_id"] == m["mission_id"]
                    assert u["status"] == ("reserved" if m["status"] in {"loading", "repositioning"} else "in_transit")
                    assert u["blood_type"] == m["blood_type"] and u["expiry_date"] > m["arrival_at"][:10]
        assert len(active_ids) == len(set(active_ids)), "Unit promised twice"
        assert set(active_ids) == {u["unit_id"] for u in self.units.values() if u["status"] in {"reserved", "in_transit"}}
        used = [uid for r in self.requests for uid in r["fulfilled_unit_ids"]]
        assert len(used) == len(set(used)), "Unit consumed twice"
        assert sum(u["status"] == "used" for u in self.units.values()) == self.initial_used + len(used)
        for r in self.requests:
            assert 0 <= r["fulfilled"] <= r["units"]
            for uid in r["fulfilled_unit_ids"]:
                u = self.units[uid]
                assert u["status"] == "used" and u["blood_type"] == r["blood_type"] and u["site_id"] == r["site_id"]
        for d in self.drones.values():
            live = [m for m in self.missions if m["drone_id"] == d["drone_id"] and m["status"] in {"repositioning", "loading", "flying", "unloading"}]
            assert len(live) <= 1, "Drone double-booked"
        assert all(u["status"] in {"available", "reserved", "in_transit", "used", "expired"} for u in self.units.values())

    def snapshot(self):
        sites = []
        for sid, site in self.sites.items():
            counts = {b: Counter(u["status"] for u in self.units.values() if u["site_id"] == sid and u["blood_type"] == b) for b in self.groups}
            sites.append({**site, "stock": {b: {k: counts[b][k] for k in ["available", "reserved"]} for b in self.groups},
                          "available": sum(c["available"] for c in counts.values())})
        totals = Counter(u["status"] for u in self.units.values())
        return deepcopy({"clock": iso(self.now), "timestamp": self.now, "end": iso(self.end), "mode": self.controller.mode,
            "version": self.version, "scheduler": self.scheduler, "planning": self.planning,
            "diagnostics": self.diagnostics, "experiments": self.experiments,
            "sites": sites, "drones": list(self.drones.values()), "drone_config": self.drone_config,
            "requests": self.requests, "missions": self.missions, "social": self.reports, "decisions": self.decisions,
            "log": self.log[-80:], "blocked_routes": sorted(self.blocked), "finished": not self.queue,
            "stats": {"available": totals["available"], "reserved": totals["reserved"], "in_transit": totals["in_transit"],
                "requested": sum(r["units"] for r in self.requests), "fulfilled": sum(r["fulfilled"] for r in self.requests),
                "unmet_at_deadline": sum(r["units"]-r["fulfilled"] for r in self.requests if r["status"] == "missed"),
                "expired": totals["expired"], "api_calls": self.controller.client.calls-self.api_start[0] if self.controller.client else 0,
                "api_successes": self.controller.client.successes-self.api_start[1] if self.controller.client else 0,
                "api_budget_remaining": max(0, self.controller.client.max_calls-self.controller.client.calls) if self.controller.client and hasattr(self.controller.client, "max_calls") else None,
                "fallbacks": sum(d["origin"] == "algorithm_fallback" for d in self.decisions)+sum(r["origin"] == "algorithm_fallback" for r in self.reports),
                "missions": sum(m["status"] == "delivered" for m in self.missions), "conservation": "PASS"}})

    def capture(self):
        if not self.analysis:
            self.frames.append(self.snapshot())

    def export(self, folder):
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        result = {"schema": "drone-demo-v1", "is_synthetic": True, "source": self.controller.mode,
                  "assumptions": {"flight": self.drone_config, "reserve": "one baseline day at banks; max baseline, daily planned demand, pending requests at donor hospitals",
                    "demand": "planned totals at 09:00; residual max(0, ceil(baseline)-planned) at 15:00; explicit emergencies added separately",
                    "transport": "straight line flight geometry; payload counted in packaged units; cold chain assumed; no midflight diversion; no external supplier missions"},
                  "summary": self.snapshot()["stats"], "frames": self.frames}
        (folder / "replay.json").write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        (folder / "final-state.json").write_text(json.dumps({"units": self.units, "state": self.snapshot()}, ensure_ascii=False), encoding="utf-8")
        return result["summary"]
