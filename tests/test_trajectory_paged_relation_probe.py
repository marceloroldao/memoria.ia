import copy
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from trajectory_paged_relation_probe import collect_pages, join_pages, resolve_paged_region, probe
from trajectory_native_evidence_join_probe import adapt_regions
from trajectory_response_quality_probe import encode


def fixture():
    rows = [dict(hierarchy_id='conversation:a', source_id=source, sequence=sequence,
                 text=text, source_kind='user_turn',
                 reply_to=None if sequence == 1 else dict(source_id='q', sequence=1))
            for source, sequence, text in [('q', 1, 'opaque q'), ('a', 2, 'value'),
                                          ('b', 3, 'rival'), ('echo', 4, 'opaque q')]]
    witnesses = [dict(hierarchy_id=r['hierarchy_id'],
        question=dict(source_id='q', source_kind='user_turn', sequence=1, match='EXACT'),
        reply=dict(source_id=r['source_id'], source_kind='user_turn', sequence=r['sequence'],
                   text=r['text'], trail_address='native-' + r['source_id'],
                   repeats_query=r['source_id'] == 'echo', group_index=None if r['source_id'] == 'echo' else i))
        for i, r in enumerate(rows[1:])]
    memory, origins = adapt_regions(rows)
    root = next(root for root in origins if memory.expand(root) == encode('value', 'unicode'))
    structural = dict(requested_region='conversation:a', packet=dict(
        query=encode('opaque q', 'unicode'), candidates=[dict(payload_id=root)]))
    return rows, witnesses, structural


class Pages:
    def __init__(self, witnesses, mutation=None):
        self.witnesses, self.mutation, self.requests = witnesses, mutation, []

    def call(self, name, request):
        self.requests.append(copy.deepcopy(request))
        offset, limit = request['offset'], request['limit']
        values = copy.deepcopy(self.witnesses[offset:offset + limit])
        end = offset + len(values)
        packet = dict(qualified=False, selection_used=False, relation='reply_to',
            explicit_reply_occurrences=len(self.witnesses), distinct_reply_trails=2,
            embedded_question_links=0, repeat_question_links=1,
            witnesses=values, page=dict(offset=offset, returned=len(values),
                                       next_offset=end if end < len(self.witnesses) else None))
        if self.mutation:
            self.mutation(packet, len(self.requests))
        return 2, packet


class PagedRelationTests(unittest.TestCase):
    def test_all_pages_keep_echo_and_page_size_does_not_change_view(self):
        rows, witnesses, structural = fixture()
        before = copy.deepcopy((rows, witnesses, structural))
        views = [join_pages(rows, 'conversation:a', 'opaque q', structural,
                            collect_pages(Pages(witnesses), 'opaque q', n)) for n in (1, 2, 64)]
        self.assertEqual(views[0], views[1])
        self.assertEqual(views[0], views[2])
        self.assertEqual(len(views[0]['episodes'][0]['relations']), 3)
        self.assertEqual(views[0]['episodes'][0]['relations'][-1]['origin'], ('conversation:a', 'echo', 4))
        self.assertTrue(views[0]['episodes'][0]['relations'][-1]['native_query_echo'])
        self.assertFalse(views[0]['episodes'][1]['relations'])
        self.assertEqual((rows, witnesses, structural), before)

    def test_early_stop_skip_duplicate_and_changing_totals_are_rejected(self):
        _, witnesses, _ = fixture()
        def early(packet, call): packet['page']['next_offset'] = None
        def skip(packet, call): packet['page']['next_offset'] = 2
        def total(packet, call): packet['explicit_reply_occurrences'] += call - 1
        def duplicate(packet, call):
            if call == 2: packet['witnesses'][0] = copy.deepcopy(witnesses[0])
        for mutation in (early, skip, total, duplicate):
            with self.subTest(mutation=mutation.__name__), self.assertRaises(ValueError):
                collect_pages(Pages(witnesses, mutation), 'opaque q', 1)

    def test_qualified_contract_and_echo_count_mismatch_are_rejected(self):
        _, witnesses, _ = fixture()
        for key, value in [('qualified', True), ('answer', 'invented'), ('selection_used', True),
                           ('relation', 'inferred'), ('repeat_question_links', 0)]:
            def mutation(packet, call): packet[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                collect_pages(Pages(witnesses, mutation), 'opaque q', 1)

    def test_missing_or_forged_local_provenance_is_rejected(self):
        rows, witnesses, structural = fixture()
        collection = collect_pages(Pages(witnesses), 'opaque q', 64)
        for mutation in ('missing', 'text', 'target', 'scope'):
            changed = copy.deepcopy(collection)
            data = copy.deepcopy(rows)
            if mutation == 'missing': changed['witnesses'].pop()
            elif mutation == 'text': changed['witnesses'][0]['reply']['text'] = 'fabricated'
            elif mutation == 'target': data[1]['reply_to']['sequence'] = 4
            else: structural = dict(structural, requested_region='conversation:b')
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                join_pages(data, 'conversation:a', 'opaque q', structural, changed)

    def test_foreign_transport_witness_is_not_local_evidence(self):
        rows, witnesses, structural = fixture()
        foreign = copy.deepcopy(witnesses[0])
        foreign['hierarchy_id'] = 'conversation:b'
        collection = collect_pages(Pages(witnesses + [foreign]), 'opaque q', 2)
        view = join_pages(rows, 'conversation:a', 'opaque q', structural, collection)
        self.assertEqual(view['excluded_other_target_witnesses'], 1)
        self.assertEqual(len(view['episodes'][0]['relations']), 3)

    def test_absent_local_target_emits_no_transport_request(self):
        rows, witnesses, _ = fixture()
        native = Pages(witnesses)
        result = resolve_paged_region(native, rows, 'conversation:unknown', 'opaque q', 1)
        self.assertEqual(native.requests, [])
        self.assertEqual(result['transport']['page_count'], 0)
        self.assertFalse(result['view']['episodes'])
        for limit in (0, 65, True, '1'):
            with self.assertRaises(ValueError):
                collect_pages(native, 'opaque q', limit)

    @unittest.skipUnless(os.environ.get('MEMORIA_NATIVE_LIBRARY'), 'requires native BDR library')
    def test_native_truncated_source_recovery_echo_address_and_cold_parity(self):
        for seed in (20261207, 20261208):
            with self.subTest(seed=seed):
                result = probe(Path(os.environ['MEMORIA_NATIVE_LIBRARY']), seed)
                self.assertEqual(result['integrity_passed'], 25)
                self.assertEqual(result['integrity_total'], 25)
                self.assertEqual([e['collection']['page_count'] for e in result['evaluations']], [25, 4, 1])
                self.assertEqual(len({e['scoped_results_sha256'] for e in result['evaluations']}), 1)


if __name__ == '__main__':
    unittest.main()
