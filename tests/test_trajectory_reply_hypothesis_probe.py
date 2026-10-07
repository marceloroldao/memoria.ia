import copy
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from trajectory_reply_hypothesis_probe import reply_hypothesis, unsafe_comparators, probe


TARGET = ('conversation:opaque', 'q', 1)


def relation(root='root-a', sequence=2, target=TARGET, echo=False):
    return dict(origin=(target[0], 'source-' + str(sequence), sequence), target=target,
                payload_id=root, native_query_echo=echo, native_trail_address='test-trail')


def recovery(episodes):
    return dict(status='OK', outcome=dict(status='OK', consistency=dict(
        status='REGIONAL_TOKEN_UNCHANGED', region=TARGET[0], global_snapshot_guaranteed=False),
        view=dict(region=TARGET[0], answer=None, qualified=False, selection_used=False, selected_target=None,
                  evidence_scope='exact_observed_target_addresses', episodes=episodes,
                  structural=dict(packet=dict(candidates=[dict(payload_id='root-a'), dict(payload_id='root-b')])))))


def episode(relations, target=TARGET):
    return dict(target=target, relations=relations, linked_roots_outside_structural_candidates=[])


class ReplyHypothesisTests(unittest.TestCase):
    def test_one_root_is_only_an_unqualified_proposal_and_copies_keep_origins(self):
        data = recovery([episode([relation(sequence=i) for i in range(2, 23)])])
        result = reply_hypothesis(data)
        self.assertEqual(result['status'], 'PROPOSAL')
        self.assertEqual(result['proposal_payload_id'], 'root-a')
        self.assertEqual(len(result['proposal_origins']), 21)
        self.assertIsNone(result['answer'])
        self.assertFalse(result['qualified'])
        self.assertFalse(result['selection_used'])
        self.assertIsNone(result['selected_target'])

    def test_repeated_conflict_abstains_while_majority_comparator_selects(self):
        data = recovery([episode([relation(sequence=i) for i in range(2, 23)] + [relation('root-b', 23)])])
        result = reply_hypothesis(data)
        self.assertEqual(result['reason'], 'COMPETING_REPLIES')
        self.assertIsNone(result['proposal_payload_id'])
        self.assertEqual([len(a['origins']) for a in result['episodes'][0]['alternatives']], [21, 1])
        self.assertEqual(unsafe_comparators(data)['occurrence_majority'], 'root-a')

    def test_same_root_in_multiple_episodes_does_not_resolve_intended_target(self):
        second = (TARGET[0], 'other-q', 4)
        data = recovery([episode([relation()]), episode([relation(sequence=5, target=second)], second)])
        result = reply_hypothesis(data)
        self.assertEqual(result['reason'], 'AMBIGUOUS_TARGETS')
        self.assertEqual(len(result['episodes']), 2)
        self.assertEqual(unsafe_comparators(data)['pooled_unique_reply'], 'root-a')

    def test_echoes_remain_addressable_without_becoming_reply_alternatives(self):
        echo = relation('query-root', 3, echo=True)
        result = reply_hypothesis(recovery([episode([echo])]))
        self.assertEqual(result['reason'], 'NO_DISTINCT_REPLY')
        self.assertEqual(result['episodes'][0]['query_echo_relations'], [echo])
        mixed = reply_hypothesis(recovery([episode([relation(), echo])]))
        self.assertEqual(mixed['proposal_payload_id'], 'root-a')
        self.assertEqual(len(mixed['proposal_origins']), 1)

    def test_unavailable_recovery_and_qualified_or_partial_contracts_are_rejected(self):
        unavailable = dict(status='EXHAUSTED', outcome=dict(view=None))
        self.assertEqual(reply_hypothesis(unavailable)['status'], 'UNAVAILABLE')
        with self.assertRaises(ValueError):
            reply_hypothesis(dict(status='EXHAUSTED', outcome=dict(view={})))
        for key, value in [('qualified', True), ('answer', 'invented'), ('selection_used', True),
                           ('selected_target', TARGET), ('evidence_scope', 'global')]:
            data = recovery([episode([relation()])])
            data['outcome']['view'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                reply_hypothesis(data)

    def test_duplicate_foreign_misaddressed_and_noncausal_relations_fail_closed(self):
        for mode in ('duplicate-target', 'duplicate-origin', 'foreign', 'target', 'noncausal', 'echo-type'):
            data = recovery([episode([relation()])])
            relations = data['outcome']['view']['episodes'][0]['relations']
            if mode == 'duplicate-target': data['outcome']['view']['episodes'].append(copy.deepcopy(episode([])))
            elif mode == 'duplicate-origin': relations.append(copy.deepcopy(relations[0]))
            elif mode == 'foreign': relations[0]['origin'] = ('conversation:foreign', 'source', 2)
            elif mode == 'target': relations[0]['target'] = (TARGET[0], 'other', 1)
            elif mode == 'noncausal': relations[0]['origin'] = (TARGET[0], 'source', 1)
            else: relations[0]['native_query_echo'] = 1
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                reply_hypothesis(data)

    def test_read_only_decision_does_not_depend_on_address_spelling(self):
        data = recovery([episode([relation()])])
        before = copy.deepcopy(data)
        result = reply_hypothesis(data)
        self.assertEqual(data, before)
        renamed = copy.deepcopy(data)
        renamed['outcome']['consistency']['region'] = 'conversation:renamed'
        view = renamed['outcome']['view']
        view['region'] = 'conversation:renamed'
        target = ('conversation:renamed', 'opaque-address', 1)
        view['episodes'][0]['target'] = target
        view['episodes'][0]['relations'][0]['target'] = target
        view['episodes'][0]['relations'][0]['origin'] = ('conversation:renamed', 'opaque-source', 2)
        changed = reply_hypothesis(renamed)
        self.assertEqual((changed['status'], changed['reason'], changed['proposal_payload_id']),
                         (result['status'], result['reason'], result['proposal_payload_id']))

    @unittest.skipUnless(os.environ.get('MEMORIA_NATIVE_LIBRARY'), 'requires native BDR library')
    def test_native_proposals_abstention_comparators_and_hidden_role_failures(self):
        for seed in (20261213, 20261214):
            result = probe(Path(os.environ['MEMORIA_NATIVE_LIBRARY']), seed)
            self.assertEqual((result['integrity_passed'], result['integrity_total']), (106, 106))
            self.assertEqual(result['relation_contract_counts'], dict(cases=13, passed=13))
            self.assertEqual(result['hidden_role_twins']['answer_passed'], 1)
            self.assertEqual(result['hidden_role_twins']['unsafe_promotion_passed'], 1)
            self.assertEqual(result['semantic_quality_status'], 'FAIL_HIDDEN_ROLE_TWINS')
            self.assertEqual(result['factual_quality_status'], 'NOT_EVALUATED')


if __name__ == '__main__':
    unittest.main()
