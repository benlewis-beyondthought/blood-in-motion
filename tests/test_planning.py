from copy import deepcopy
import json
import unittest
from tempfile import TemporaryDirectory
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import threading
from blood_response.dispatch import Simulation, iso, stamp
from blood_response.planning import choose, diagnose, fork_known, what_helps
from blood_response.dispatch_server import App, handler
from blood_response.decisions import Controller


def request(s, **kwargs):
    return dict(dict(site_id='H1', blood_type='O-', units=4, deadline=iso(s.now+3600), priority='critical', source='test'), **kwargs)


class PlanningTests(unittest.TestCase):
    def test_known_fork_excludes_future_incidents_and_credentials(self):
        s=Simulation(scripted=False)
        at=s.now+60
        for kind,payload in [('social',{}),('route',{}),('receipt',{}),
                             ('request',request(s,source='scenario_emergency')),
                             ('request',request(s,source='planned'))]:
            s.enqueue(at,kind,payload)
        c=fork_known(s,at+3600)
        self.assertEqual([(e[2],e[3].get('source')) for e in c.queue],[('request','planned')])
        self.assertIsNone(c.controller.client)
        self.assertFalse(c.frames)

    def test_rolling_serves_more_critical_units_in_competing_case(self):
        results=[]
        for scheduler in ['greedy','rolling']:
            s=Simulation(scripted=False,scheduler=scheduler)
            s.baseline={};s.planned=[]
            s.drones={'D1':s.drones['D1']}
            for u in s.units.values():
                if not (u['site_id']=='B1' and u['blood_type']=='O-' and u['status']=='available'):
                    u['status']='used'
            s.initial_used=sum(u['status']=='used' for u in s.units.values())
            for site,lat in [('B1',48.85),('H1',49.0),('H2',48.86)]:
                s.sites[site].update(lat=lat,lon=2.35)
            s.add_request(request(s,units=1,deadline=iso(s.now+22*60)))
            s.add_request(request(s,site_id='H2',units=4,deadline=iso(s.now+23*60)))
            s.allocate()
            if scheduler=='rolling':
                self.assertEqual(s.planning['selected']['projected_fulfilled'][0],4)
                self.assertEqual(s.planning['baseline']['projected_fulfilled'][0],1)
            while s.queue:s.step()
            s.check()
            results.append(sum(r['fulfilled'] for r in s.requests))
        self.assertEqual(results,[1,4])

    def test_shortage_constraints_can_overlap(self):
        s=Simulation(scripted=False)
        r=s.add_request(request(s,units=100,deadline=iso(s.now+60)))
        d=diagnose(s,r)
        self.assertIn('INSUFFICIENT_AVAILABLE_GROUP',d['flags'])
        self.assertIn('STOCK_PROTECTED_BY_RESERVE',d['flags'])
        self.assertIn('DEADLINE_OR_MISSION_LIMIT',d['flags'])
        self.assertIn('NO_IMMEDIATE_FEASIBLE_DISPATCH',d['flags'])

    def test_counterfactuals_are_isolated_and_no_paid_calls(self):
        s=Simulation(scripted=False,scheduler='rolling')
        r=s.inject(request(s,units=40,deadline=iso(s.now+60)))
        before=json.dumps(s.snapshot(),sort_keys=True)
        units=deepcopy(s.units);queue=deepcopy(s.queue)
        result=s.what_helps(r['request_id'])
        self.assertEqual(result['results'][0]['fulfilled'],0)
        self.assertEqual(result['results'][-1]['additional_units'],8)
        self.assertEqual(s.units,units);self.assertEqual(s.queue,queue)
        actual=s.snapshot();actual['experiments']={}
        self.assertEqual(json.dumps(actual,sort_keys=True),before)
        self.assertEqual(s.what_helps(r['request_id']),result)

    def test_deadline_retains_predeadline_diagnostic(self):
        s=Simulation(scripted=False)
        r=s.inject(request(s,units=40,deadline=iso(s.now+60)))
        observed=s.diagnostics[0]['as_of']
        s.step()
        self.assertEqual(r['status'],'missed')
        self.assertEqual(s.diagnostics[0]['as_of'],observed)
        self.assertLess(stamp(observed),stamp(r['deadline']))

    def test_search_does_not_mutate_live_state(self):
        s=Simulation(scripted=False,scheduler='rolling')
        s.add_request(request(s))
        before=deepcopy(s.__dict__)
        selected,summary=choose(s)
        self.assertIn(selected,s.plans(s.requests[0]))
        self.assertLessEqual(len(summary['alternatives']),12)
        self.assertEqual(s.units,before['units']);self.assertEqual(s.queue,before['queue'])
        self.assertEqual(s.missions,[]);self.assertEqual(s.controller.client,None)

    def test_future_emergency_does_not_change_choice(self):
        s=Simulation(scripted=False,scheduler='rolling')
        s.add_request(request(s))
        first,_=choose(s)
        s.enqueue(s.now+60,'request',request(s,site_id='H4',units=100))
        second,_=choose(s)
        self.assertEqual(first,second)

    def test_http_what_if_is_saved_and_operational_state_is_unchanged(self):
        from pathlib import Path
        with TemporaryDirectory() as folder:
            app=App(Controller(),Path(folder)/'run',scheduler='rolling')
            server=ThreadingHTTPServer(('127.0.0.1',0),handler(app))
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            def post(path,body):
                req=Request(f'http://127.0.0.1:{server.server_port}'+path,data=json.dumps(body).encode(),headers={'Content-Type':'application/json','X-Demo-Token':app.token})
                with urlopen(req) as response:return json.load(response)
            try:
                state=post('/api/request',dict(site_id='H1',blood_type='O-',units=40,priority='critical',deadline_minutes=1))
                result=post('/api/what-if',{'request_id':state['requests'][0]['request_id']})
                self.assertEqual(state['stats'],result['stats'])
                self.assertTrue(app.sim.frames[-1]['experiments'])
                self.assertEqual(result['scheduler'],'rolling')
                with self.assertRaises(HTTPError) as error:post('/api/what-if',{'request_id':'missing'})
                self.assertEqual(error.exception.code,400)
            finally:
                server.shutdown();server.server_close();thread.join()


if __name__=='__main__':unittest.main()
