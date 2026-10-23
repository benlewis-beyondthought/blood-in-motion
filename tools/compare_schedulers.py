"""Paired deterministic weekend comparison; no paid API calls or future oracle."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from blood_response.dispatch import Simulation, iso
from blood_response.model import DEFAULT_DATA


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in DEFAULT_DATA.rglob('*') if p.is_file()}
    runs={};signatures={}
    for scheduler in ['greedy','rolling']:
        sim=Simulation(scheduler=scheduler)
        start=time.monotonic()
        sim.inject(dict(site_id='H1',blood_type='O-',units=8,deadline=iso(sim.now+2700),priority='critical',source='manual_demo_request'))
        steps=0
        while sim.queue:
            sim.step();steps+=1
            if steps%75==0:print(f'{scheduler}: {steps} events',flush=True)
        elapsed=round(time.monotonic()-start,3)
        missed=Counter()
        for r in sim.requests:
            if r['status']=='missed':missed[r['priority']]+=r['units']-r['fulfilled']
        # Export a representative isolated experiment for replay and audit.
        if sim.diagnostics:
            sim.what_helps(sim.diagnostics[0]['request_id'])
            sim.capture()
        stats=sim.export(args.output/scheduler)
        signatures[scheduler]=[(r['site_id'],r['blood_type'],r['units'],r['deadline'],r['priority'],r['created_at']) for r in sim.requests]
        runs[scheduler]={'stats':stats,'unmet_by_priority':dict(missed),'elapsed_seconds':elapsed,
                         'decisions':len(sim.decisions),'missed_requests':sum(r['status']=='missed' for r in sim.requests)}
        print(scheduler,json.dumps(runs[scheduler]),flush=True)
    assert signatures['greedy']==signatures['rolling']
    assert hashes=={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in DEFAULT_DATA.rglob('*') if p.is_file()}
    # Pin the established baseline outcome including the same initial request.
    assert runs['greedy']['stats']['fulfilled']==392
    assert runs['greedy']['stats']['unmet_at_deadline']==77
    report={'scope':'Same synthetic weekend plus identical initial 8-unit request; deterministic controllers',
            'runs':runs,'identical_requests':True,'canonical_hashes_unchanged':True,
            'additional_units_fulfilled':runs['rolling']['stats']['fulfilled']-runs['greedy']['stats']['fulfilled'],
            'limitation':'One authored scenario. Rolling search is bounded, not globally optimal. No new model benchmark or clinical validation.'}
    (args.output/'comparison.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
