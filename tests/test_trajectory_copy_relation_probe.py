import copy
import os
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from trajectory_copy_relation_probe import copy_relations,fixture,probe
from trajectory_inferred_relation_probe import score


class CopyRelationTests(unittest.TestCase):
    def read(self,case):
        rows,region,query,reference=fixture(20261219,case)
        return rows,copy_relations(rows,region,query),reference

    def test_observed_context_switches_addressed_root_without_hidden_role(self):
        results=[]
        for case,source in [('matched_context','a'),('switched_context','b')]:
            rows,view,reference=self.read(case)
            route=view['routes']['positive_copy_witness']
            self.assertIsNotNone(route['proposal_payload_id'])
            self.assertEqual([r['origin'][1] for e in route['episodes'] for r in e['inferred_relations']],[source])
            self.assertTrue(score(view,reference,rows)['positive_copy_witness']['exact_relation_set'])
            self.assertIsNone(route['answer']);self.assertFalse(route['qualified'])
            self.assertFalse(route['selection_used']);self.assertIsNone(route['selected_target'])
            results.append(route['proposal_payload_id'])
        self.assertNotEqual(*results)

    def test_same_context_conflict_and_copies_preserve_all_origins_without_voting(self):
        rows,view,reference=self.read('repeated_conflict')
        route=view['routes']['positive_copy_witness']
        self.assertIsNone(route['proposal_payload_id'])
        self.assertEqual(route['reason'],'COMPETING_INFERRED_ROOTS')
        relations=route['episodes'][0]['inferred_relations']
        self.assertEqual(len(relations),22)
        self.assertEqual(len({tuple(r['origin']) for r in relations}),22)
        self.assertEqual(len({r['payload_id'] for r in relations}),2)
        self.assertTrue(score(view,reference,rows)['positive_copy_witness']['exact_relation_set'])

    def test_unknown_cuts_are_retained_and_never_declared_globally_excluded(self):
        _,view,_=self.read('matched_context')
        self.assertTrue(view['unknown_cuts'])
        self.assertTrue(all(not c['cut_excluded'] for c in view['unknown_cuts']))
        self.assertFalse(view['cut_exclusion_used'])
        self.assertFalse(view['global_reply_exclusion_guaranteed'])
        self.assertTrue(all(r['positive_copy_witnesses'] for e in view['routes']['positive_copy_witness']['episodes']
                            for r in e['inferred_relations']))

    def test_links_are_masked_read_is_immutable_and_unrelated_twin_still_fails(self):
        rows,region,query,reference=fixture(20261219,'matched_context')
        before=copy.deepcopy(rows)
        view=copy_relations(rows,region,query)
        self.assertEqual(rows,before)
        rows[-2]['reply_to']=dict(source_id='other',sequence=999)
        self.assertEqual(copy_relations(rows,region,query),view)
        negative=score(view,[],rows)['positive_copy_witness']
        self.assertEqual(negative['false_positive'],1)
        self.assertFalse(negative['exact_relation_set'])

    def test_generated_barrier_and_foreign_matching_root_do_not_supply_local_origins(self):
        for case in ('generated_barrier','foreign_matching_root'):
            _,view,_=self.read(case)
            self.assertEqual(view['routes']['positive_copy_witness']['episodes'][0]['inferred_relations'],[])
            self.assertIsNone(view['routes']['positive_copy_witness']['proposal_payload_id'])

    def test_two_occurrences_remain_distinct_without_selecting_intended_target(self):
        _,view,_=self.read('multiple_targets')
        route=view['routes']['positive_copy_witness']
        self.assertEqual(len(route['episodes']),2)
        self.assertNotEqual(route['episodes'][0]['target'],route['episodes'][1]['target'])
        self.assertIsNone(route['proposal_payload_id'])
        self.assertEqual(route['reason'],'AMBIGUOUS_TARGETS')

    def test_missing_or_unknown_context_is_not_replaced_by_global_fallback(self):
        for case in ('unknown_context','missing_context'):
            _,view,_=self.read(case)
            self.assertIsNone(view['routes']['positive_copy_witness']['proposal_payload_id'])
            self.assertFalse(view['global_reply_exclusion_guaranteed'])

    @unittest.skipUnless(os.environ.get('MEMORIA_NATIVE_LIBRARY'),'requires native BDR library')
    def test_native_controls_keep_quality_failures_and_cold_full_parity(self):
        for seed in (20261219,20261220):
            result=probe(Path(os.environ['MEMORIA_NATIVE_LIBRARY']),seed)
            self.assertEqual(result['integrity_passed'],result['integrity_total'])
            self.assertEqual(len(result['cases']),12)
            self.assertEqual(result['hidden_relation_twins']['route_matches']['positive_copy_witness'],1)
            totals=result['route_totals']['positive_copy_witness']
            self.assertGreater(totals['true_positive'],1)
            self.assertGreater(totals['false_positive'],0)
            self.assertGreater(totals['false_negative'],0)
            self.assertEqual(result['relation_quality_status'],'FAIL_FALSE_OR_MISSING_RELATIONS')
            self.assertEqual(result['factual_quality_status'],'NOT_EVALUATED')


if __name__=='__main__':unittest.main()
