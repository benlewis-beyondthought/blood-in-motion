"""Bounded rolling-horizon search and isolated counterfactuals, not a global optimum."""
from copy import deepcopy
import heapq
import math
from .decisions import Controller

HORIZON_MINUTES = 90
MAX_CANDIDATES = 12


def fork_known(sim, until):
    """Copy operational state only. Never copy a client/key or unreleased incident."""
    clone = object.__new__(type(sim))
    omitted = {'controller', 'frames', 'checkpoints', 'experiments', 'planning', 'diagnostics', 'decisions', 'log', 'reports', 'queue', '_available_index'}
    for key, value in sim.__dict__.items():
        if key not in omitted:
            setattr(clone, key, deepcopy(value))
    clone.controller = Controller()
    clone._available_index = None
    clone.api_start = (0, 0)
    clone.frames, clone.checkpoints, clone.experiments = [], {}, {}
    clone.decisions, clone.log, clone.reports = [], [], []
    clone.diagnostics, clone.planning = [], None
    clone.scheduler, clone.analysis = 'greedy', True
    # Mission events already committed, current request deadlines and calendar expiry
    # are known. Future social, emergencies, closures and receipts are not known.
    known = {'load', 'depart', 'land', 'arrive', 'release_drone', 'deadline', 'expiry'}
    clone.queue = [deepcopy(e) for e in sim.queue if e[0] <= until and
                   (e[2] in known or (e[2] == 'request' and e[3].get('source') == 'planned'))]
    heapq.heapify(clone.queue)
    return clone


def rollout(sim, until):
    sim.allocate()
    while sim.queue and sim.queue[0][0] <= until:
        sim.step()
    sim.check()
    return sim


def fulfilled(sim):
    return tuple(sum(r['fulfilled'] for r in sim.requests if r['priority'] == p)
                 for p in ['critical', 'scheduled', 'routine'])


def choose(sim):
    """Evaluate initial actions followed by greedy continuation on the known state."""
    from .dispatch import iso
    candidates = []
    for request in sim.pending():
        candidates.extend(sim.plans(request)[:2])
        if len(candidates) >= MAX_CANDIDATES:
            break
    candidates = candidates[:MAX_CANDIDATES]
    if not candidates:
        return None, None
    until = min(sim.end, sim.now + HORIZON_MINUTES*60)
    rows = []
    for plan in candidates:
        trial = fork_known(sim, until)
        before = fulfilled(trial)
        start_missions = len(trial.missions)
        trial.dispatch(plan, {'decision_id': 'LOOKAHEAD'})
        rollout(trial, until)
        gain = tuple(a-b for a, b in zip(fulfilled(trial), before))
        distance = round(sum(m['reposition_km']+m['delivery_km'] for m in trial.missions[start_missions:]), 3)
        rows.append({'request_id': plan['request_id'], 'plan_id': plan['plan_id'],
                     'source': plan['from_site_id'], 'destination': plan['to_site_id'],
                     'drone_id': plan['drone_id'], 'units': plan['units'],
                     'projected_fulfilled': list(gain), 'projected_flight_km': distance,
                     'arrival_at': plan['arrival_at']})
    # Strict priority order; then travel. Stable final tie uses baseline order.
    best = max(range(len(rows)), key=lambda i: (*rows[i]['projected_fulfilled'], -rows[i]['projected_flight_km']))
    selected = candidates[best]
    summary = {'as_of': iso(sim.now), 'horizon_end': iso(until),
               'method': 'Bounded rollout: up to 12 initial actions, greedy continuation',
               'objective': 'Critical, then scheduled, then routine units delivered; then less flight distance',
               'knowledge': 'Current requests, committed missions and published planned activity only',
               'selected': rows[best], 'baseline': rows[0], 'alternatives': rows,
               'candidate_limit': MAX_CANDIDATES, 'globally_optimal': False}
    return selected, summary


def diagnose(sim, request):
    from .dispatch import iso, km, stamp
    blood, target = request['blood_type'], request['site_id']
    need = max(0, request['units']-request['fulfilled']-sim.committed(request))
    sources = []
    for sid in sim.sites:
        if sid == target:
            continue
        stock = len(sim.available(sid, blood))
        reserve = sim.reserve(sid, blood)
        routes = []
        for drone in sim.drones.values():
            cfg = sim.drone_config
            travel = (km(sim.sites[drone['site_id']], sim.sites[sid])+km(sim.sites[sid], sim.sites[target]))/cfg['speed_kmh']*60
            minutes = travel+cfg['load_minutes']+cfg['unload_minutes']
            # Busy positions are not a usable ETA; only idle estimates are reported.
            blocked = (sid, target) in sim.blocked or (drone['site_id'] != sid and (drone['site_id'], sid) in sim.blocked)
            routes.append({'drone_id': drone['drone_id'], 'idle': drone['status'] == 'idle',
                           'blocked': blocked,
                           'arrival_at': iso(sim.now+math.ceil(minutes*60)) if drone['status'] == 'idle' else None,
                           'within_limits': minutes <= cfg['max_mission_minutes'] and sim.now+math.ceil(minutes*60) <= stamp(request['deadline']) if drone['status'] == 'idle' else False})
        sources.append({'site_id': sid, 'available': stock, 'reserve': reserve,
                        'releasable': max(0, stock-reserve), 'routes': routes})
    flags = []
    local = len(sim.available(target, blood))
    if sum(s['available'] for s in sources)+local < need:
        flags.append('INSUFFICIENT_AVAILABLE_GROUP')
    if any(s['available'] and s['reserve'] for s in sources):
        flags.append('STOCK_PROTECTED_BY_RESERVE')
    if not any(d['status'] == 'idle' for d in sim.drones.values()):
        flags.append('ALL_DRONES_BUSY')
    if any(s['releasable'] and any(r['blocked'] for r in s['routes']) for s in sources):
        flags.append('ROUTE_RESTRICTION')
    if any(s['releasable'] and any(r['idle'] and not r['blocked'] and not r['within_limits'] for r in s['routes']) for s in sources):
        flags.append('DEADLINE_OR_MISSION_LIMIT')
    options = sim.plans(request)
    if not options and need:
        flags.append('NO_IMMEDIATE_FEASIBLE_DISPATCH')
    if options:
        flags.append('FEASIBLE_BUT_COMPETING_FOR_FLEET')
    return {'request_id': request['request_id'], 'site_id': target, 'blood_type': blood,
            'as_of': iso(sim.now), 'uncommitted_units': need, 'committed_units': sim.committed(request),
            'local_available': local, 'flags': flags, 'sources': sources,
            'interpretation': 'Observed constraints may overlap; this is not proof of a unique cause.'}


def what_helps(checkpoint, request_id):
    from .dispatch import iso, stamp
    request = next(r for r in checkpoint.requests if r['request_id'] == request_id)
    until = min(checkpoint.end, stamp(request['deadline']))
    variants = [('baseline', 'No change'), ('drone_b1', 'One extra drone at B1'),
                ('drone_b2', 'One extra drone at B2'), ('stock', 'Eight usable units received at requesting hospital')]
    results = []
    for key, label in variants:
        trial = fork_known(checkpoint, until)
        if key.startswith('drone'):
            trial.drones['WHATIF'] = {'drone_id': 'WHATIF', 'site_id': key[-2:].upper(), 'status': 'idle', 'mission_id': None}
        elif key == 'stock':
            trial.process('receipt', {'site_id': request['site_id'], 'blood_type': request['blood_type'], 'units': 8})
        rollout(trial, until)
        target = next(r for r in trial.requests if r['request_id'] == request_id)
        results.append({'id': key, 'label': label, 'fulfilled': target['fulfilled'],
                        'unmet': target['units']-target['fulfilled'], 'system_fulfilled': list(fulfilled(trial))})
    for row in results:
        row['additional_units'] = row['fulfilled']-results[0]['fulfilled']
        row['system_delta'] = [a-b for a,b in zip(row['system_fulfilled'], results[0]['system_fulfilled'])]
    return {'request_id': request_id, 'as_of': iso(checkpoint.now), 'until': iso(until), 'results': results,
            'method': 'Isolated greedy continuations from the first unresolved snapshot. Known evidence only; no new API calls.',
            'limitation': 'Hypothetical interventions, not forecasts or proof of causation. Later unknown events are excluded.'}
