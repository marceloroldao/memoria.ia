from functools import lru_cache
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from trajectory_cut_compatibility_probe import compact_report, compare, probe


@lru_cache(maxsize=1)
def report():
    return probe(20261126)


def primary(stage):
    return stage['cases'][0]['diagnostic']


class CutCompatibilityTests(unittest.TestCase):
    def test_mismatch_is_conditional_on_one_observed_root(self):
        for ev in report()['evaluations']:
            if ev['joined_target_copies']:
                continue
            cuts = primary(ev['stages'][0])['cuts']
            future = next(c for c in cuts if c['source_position'] == ev['fixture']['rival_cut'])
            fact = next(x for x in future['comparisons'] if x['output'] == ev['fixture']['fact'])
            self.assertEqual(fact['status'], 'INCOMPATIBLE_OBSERVED_ROOT')
            self.assertEqual(future['status'], 'UNKNOWN')
            self.assertFalse(future['cut_excluded'])
            self.assertEqual([r['observation_id'] for r in fact['occurrences']], ['fact'])

    def test_later_root_supports_previously_unknown_cut_without_erasing_first(self):
        for ev in report()['evaluations']:
            if ev['joined_target_copies']:
                continue
            first, late = primary(ev['stages'][0]), primary(ev['stages'][2])
            position = ev['fixture']['rival_cut']
            before = next(c for c in first['cuts'] if c['source_position'] == position)
            after = next(c for c in late['cuts'] if c['source_position'] == position)
            self.assertEqual((before['status'], after['status']), ('UNKNOWN', 'SUPPORTED'))
            self.assertEqual(after['supported_roots'], tuple(x['payload_id'] for x in after['comparisons'] if x['output'] == ev['fixture']['rival']))
            # The old root is still incompatible with this cut, despite new
            # evidence supporting that cut through a different observed root.
            self.assertEqual(next(x['status'] for x in after['comparisons'] if x['output'] == ev['fixture']['fact']), 'INCOMPATIBLE_OBSERVED_ROOT')
            packet = ev['stages'][2]['cases'][0]['packet']
            self.assertEqual({x['output'] for x in packet['candidates']}, {ev['fixture']['fact'], ev['fixture']['rival']})
            self.assertIsNone(packet['prior_structural_hypothesis'])

    def test_adjacent_root_equivalence_never_claims_a_unique_boundary(self):
        for ev in report()['evaluations']:
            if not ev['joined_target_copies']:
                continue
            for stage in ev['stages']:
                cuts = primary(stage)['cuts']
                self.assertEqual({c['source_position'] for c in cuts}, {2, 3, 4, 5})
                self.assertTrue(all(c['status'] == 'SUPPORTED' for c in cuts))
                self.assertEqual(len({c['supported_roots'] for c in cuts}), 1)
                self.assertEqual(primary(stage)['excluded_cuts'], ())

    def test_repetition_preserves_support_candidates_and_only_adds_occurrences(self):
        for ev in report()['evaluations']:
            for before, after in ((ev['stages'][0], ev['stages'][1]), (ev['stages'][2], ev['stages'][3])):
                a, b = primary(before), primary(after)
                view = lambda d: [(c['layout_id'], c['source_position'], c['status'], c['supported_roots']) for c in d['cuts']]
                self.assertEqual(view(a), view(b))
                self.assertEqual(a['candidate_roots'], b['candidate_roots'])
            late = primary(ev['stages'][3])
            for c in late['cuts']:
                rival = next(x for x in c['comparisons'] if x['output'] == ev['fixture']['rival'])
                self.assertEqual([r['observation_id'] for r in rival['occurrences']], ['late:rival', 'repeat:rival'])

    def test_copy_contract_distinguishes_missing_duplicate_order_and_layout(self):
        frame = dict(target_order=(0, 1), target_prefix=(10,), target_between=(20,),
                     target_bridge=(30,), target_suffix=(40,))
        slots = ((1,), (2,))
        cases = [((10, 1, 20, 2, 30, 7, 40), 'EXACT_COPIES_AND_LAYOUT'),
                 ((10, 1, 20, 3, 30, 7, 40), 'MISSING_EXACT_COPY'),
                 ((10, 1, 20, 2, 30, 1, 40), 'NONUNIQUE_EXACT_COPY'),
                 ((10, 2, 20, 1, 30, 7, 40), 'COPY_ORDER_OR_OVERLAP'),
                 ((10, 1, 21, 2, 30, 7, 40), 'FIXED_LAYOUT_OR_VALUE_MISMATCH')]
        for target, reason in cases:
            self.assertEqual(compare(frame, slots, target)['reason'], reason)

    def test_bijection_source_addresses_and_read_only_packet_parity(self):
        evaluations = report()['evaluations']
        for left, right in zip(evaluations[::2], evaluations[1::2]):
            for a, b in zip(left['stages'], right['stages']):
                rows = {r['observation_id']: r for r in a['provenance']}
                for ac, bc in zip(a['cases'], b['cases']):
                    ad, bd = ac['diagnostic'], bc['diagnostic']
                    self.assertEqual([(c['source_position'], c['status']) for c in ad['cuts']], [(c['source_position'], c['status']) for c in bd['cuts']])
                    self.assertEqual({tuple(1000000 - s for s in c['output']) for c in ac['packet']['candidates']}, {c['output'] for c in bc['packet']['candidates']})
                    self.assertEqual(ad['candidate_roots'], tuple(c['payload_id'] for c in ac['packet']['candidates']))
                    self.assertFalse(ad['qualified'])
                    self.assertIsNone(ad['answer'])
                    self.assertFalse(ac['packet']['observed_continuations'])
                    for cut in ad['cuts']:
                        for root in cut['comparisons']:
                            for occurrence in root['occurrences']:
                                self.assertEqual(occurrence, rows[occurrence['observation_id']])
                                self.assertEqual(occurrence['payload_id'], root['payload_id'])

    def test_quality_failure_and_compact_report_preserve_denominator(self):
        r = report()
        self.assertEqual((r['counts']['passed'], r['counts']['cases'], r['counts']['all_targets_retained'],
                          r['counts']['conflicts_preserved'], r['counts']['false_unique']), (28, 32, 16, 8, 0))
        self.assertEqual(r['structural_quality_status'], 'FAIL')
        self.assertEqual(r['semantic_quality_status'], 'UNQUALIFIED')
        summary = compact_report(r)
        self.assertEqual(summary['counts'], r['counts'])
        self.assertEqual(len(summary['full_report_sha256']), 64)


if __name__ == '__main__':
    unittest.main()
