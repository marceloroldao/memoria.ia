import copy
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from trajectory_borrowed_map_probe import fixture
from trajectory_witness_requests import propose
from trajectory_witness_requests_probe import scripted_response,trial


def materialize(fixture):
    region='conversation:feedback-session:'+fixture['scope']
    rows=[dict(row,hierarchy_id=region,source_id=f'row-{i}',sequence=i+1) for i,row in enumerate(fixture['rows'])]
    return region,rows


class WitnessRequestTests(unittest.TestCase):
    def test_indistinguishable_worlds_yield_same_request_without_answer(self):
        views=[]
        for world in ('shared_map','switched_map'):
            f=fixture('humidity',20261101,'uppercase','two_anchors',world);region,rows=materialize(f);saved=copy.deepcopy(rows)
            view=propose(rows,region,f['queries'][0]['text']);views.append(view)
            self.assertEqual(rows,saved);self.assertEqual(len(view['requests']),1)
            self.assertFalse(view['request_dispatched']);self.assertFalse(view['observations_recorded'])
            item=view['requests'][0]
            self.assertEqual(set(item),{'request_id','kind','source_text','source_kind','unwitnessed_source_symbols','donor_question_origins','supporting_route_ids'})
            self.assertEqual(item['source_kind'],'constructed_request')
            self.assertNotIn(item['source_text'],{q['text'] for q in f['queries']})
            self.assertNotIn(item['source_text'],{r['text'] for r in rows})
            self.assertTrue(all(s in item['source_text'] for s in item['unwitnessed_source_symbols']))
            self.assertEqual(view,propose(rows,region,f['queries'][0]['text']))
        self.assertEqual(views[0],views[1])

    def test_missing_anchor_does_not_fabricate_a_request(self):
        for arm in ('baseline','one_anchor','generated','foreign'):
            f=fixture('humidity',20261101,'uppercase',arm,'shared_map');region,rows=materialize(f)
            self.assertEqual(propose(rows,region,f['queries'][0]['text'])['requests'],[])

    def test_generated_response_does_not_resolve_request(self):
        f=fixture('humidity',20261101,'uppercase','two_anchors','shared_map');region,rows=materialize(f)
        before=propose(rows,region,f['queries'][0]['text'])
        f['rows']+=scripted_response(f,before['requests'][0],'generated');region,rows=materialize(f)
        self.assertEqual(propose(rows,region,f['queries'][0]['text']),before)

    def test_unrelated_response_does_not_resolve_request(self):
        f=fixture('humidity',20261101,'uppercase','two_anchors','shared_map');region,rows=materialize(f)
        before=propose(rows,region,f['queries'][0]['text'])
        f['rows']+=scripted_response(f,before['requests'][0],'irrelevant');region,rows=materialize(f)
        self.assertEqual(propose(rows,region,f['queries'][0]['text']),before)

    def test_observed_pair_ends_this_request_without_certifying_truth(self):
        for arm in ('observed','incorrect_observation'):
            f=fixture('humidity',20261101,'uppercase','two_anchors','shared_map');region,rows=materialize(f)
            before=propose(rows,region,f['queries'][0]['text']);f['rows']+=scripted_response(f,before['requests'][0],arm)
            region,rows=materialize(f);after=propose(rows,region,f['queries'][0]['text'])
            self.assertEqual(after['requests'],[]);self.assertFalse(after['qualified'])
            self.assertEqual(after['factual_quality_status'],'NOT_EVALUATED')


class NativeWitnessRequestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.library=Path(os.environ.get('MEMORIA_NATIVE_LIBRARY','build/trajectory-native/libmemoria_mobile.so'))
        if not cls.library.exists():raise unittest.SkipTest('native library required')

    def test_observed_response_resolves_both_worlds_after_native_restart(self):
        for world in ('shared_map','switched_map'):
            report=trial(self.library,'humidity',20261101,'uppercase',world,'observed')
            self.assertTrue(all(report['checks'].values()))
            self.assertTrue(all(c['score']['exact'] for c in report['cases']))
            self.assertEqual(report['pending_request']['requests'],[])

    def test_incorrect_declared_response_can_learn_wrong_route(self):
        for world in ('shared_map','switched_map'):
            report=trial(self.library,'humidity',20261101,'uppercase',world,'incorrect_observation')
            self.assertTrue(all(report['checks'].values()))
            for case in report['cases']:
                if case['query']['family']=='surface':
                    self.assertFalse(case['score']['exact']);self.assertEqual(case['score']['extra'],1);self.assertEqual(case['score']['missing'],1)

    def test_generated_response_stays_pending_after_restart(self):
        report=trial(self.library,'humidity',20261101,'uppercase','switched_map','generated')
        self.assertTrue(all(report['checks'].values()))
        self.assertEqual(report['request'],report['pending_request'])
