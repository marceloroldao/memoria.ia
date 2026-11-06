#!/usr/bin/env python3
"""Read-only frame analogy learned from three distinct adjacent root pairs."""
import argparse
from dataclasses import asdict, dataclass
from hashlib import blake2b
from itertools import combinations
import json
from pathlib import Path
import tempfile

from trajectory_native_bridge_probe import adapt, collect, fixtures as bridge_fixtures
from mobile_region_replay import NativeProbe
from trajectory_response_quality_probe import TrajectoryGenerationExperiment, encode


def prefix(items):
    return tuple(x[0] for x in take_equal(zip(*items)))


def take_equal(rows):
    for row in rows:
        if len(set(row)) != 1:
            break
        yield row


def suffix(items):
    return prefix([tuple(reversed(x)) for x in items])[::-1]


def occurrences(part, whole):
    return tuple(i for i in range(len(whole)-len(part)+1) if whole[i:i+len(part)] == part)


def middle(value, left, right):
    if not value[:len(left)] == left or not value[-len(right):] == right:
        return None
    stop = len(value)-len(right)
    return value[len(left):stop] if stop > len(left) else None


@dataclass(frozen=True)
class Frame:
    source_prefix: tuple
    source_suffix: tuple
    target_prefix: tuple
    target_bridge: tuple
    target_suffix: tuple
    witnesses: tuple

    @property
    def frame_id(self):
        return blake2b(repr(self).encode(), digest_size=16).hexdigest()


def learn_frames(memory):
    previous, pairs = {}, set()
    for row in memory.snapshot()['observations']:
        scope = row['hierarchy_id'], row['stream_id']
        if scope in previous and previous[scope] != row['payload_id']:
            pairs.add((previous[scope], row['payload_id'], row['stream_id']))
        previous[scope] = row['payload_id']
    frames = set()
    for group in combinations(sorted(pairs), 3):
        sources = [memory.expand(s) for s, _, _ in group]
        targets = [memory.expand(t) for _, t, _ in group]
        left, right = prefix(sources), suffix(sources)
        if not left or not right:
            continue
        variables = [middle(source, left, right) for source in sources]
        if any(v is None for v in variables) or len(set(variables)) != 3:
            continue
        positions = [occurrences(v, target) for v, target in zip(variables, targets)]
        if any(len(p) != 1 for p in positions):
            continue
        heads = [t[:p[0]] for t, p in zip(targets, positions)]
        if not heads[0] or len(set(heads)) != 1:
            continue
        tails = [t[p[0]+len(v):] for t, p, v in zip(targets, positions, variables)]
        bridge, ending = prefix(tails), suffix(tails)
        if not bridge or not ending:
            continue
        values = [middle(tail, bridge, ending) for tail in tails]
        if any(v is None for v in values) or len(set(values)) != 3:
            continue
        frames.add(Frame(left, right, heads[0], bridge, ending, group))
    return tuple(sorted(frames, key=lambda f: f.frame_id))


def recall(memory, query):
    query = tuple(query)
    frames = learn_frames(memory)
    roots = {r['payload_id'] for r in memory.snapshot()['observations']}
    candidates = {}
    for frame in frames:
        starts = occurrences(frame.source_prefix, query)
        # Two possible complete cues do not authorize choosing the last one.
        if len(starts) != 1:
            continue
        variable = middle(query[starts[0]:], frame.source_prefix, frame.source_suffix)
        if variable is None:
            continue
        head = frame.target_prefix + variable + frame.target_bridge
        for root in sorted(roots):
            if middle(memory.expand(root), head, frame.target_suffix) is not None:
                candidates.setdefault(root, []).append(frame)
    return dict(frames=tuple(asdict(f) | {'frame_id': f.frame_id} for f in frames),
        candidates=tuple(dict(payload_id=root, output=memory.expand(root),
            frame_ids=tuple(f.frame_id for f in routes),
            witnesses=tuple(sorted({w for f in routes for w in f.witnesses})))
            for root, routes in sorted(candidates.items())),
        hypothesis=memory.expand(next(iter(candidates))) if len(candidates)==1 else None,
        reason='UNIQUE_OBSERVED_FRAME_MATCH' if len(candidates)==1 else
               'COMPETING_FRAME_MATCHES' if candidates else 'NO_OBSERVED_FRAME_MATCH')


def checked_read(memory, query):
    before = memory.snapshot(), memory.learning_state()
    generation = asdict(memory.generate(query))
    result = recall(memory, query)
    cold = TrajectoryGenerationExperiment.restore(memory.snapshot())
    assert result == recall(cold, query)
    assert generation == asdict(memory.generate(query))
    assert before == (memory.snapshot(), memory.learning_state())
    return result


def fixtures():
    isolated = bridge_fixtures()[0][1]
    def row(source, scope, sequence, text, kind='user_turn'):
        return dict(source_id=source, hierarchy_id='conversation:'+scope,
                    sequence=sequence, text=text, source_kind=kind)
    subjects, names = ('barco', 'avião', 'sensor'), ('Vela', 'Nuvem', 'Pico')
    training = [r for i, (subject, name) in enumerate(zip(subjects, names)) for r in (
        row(f'train-{i}-q', f'train-{i}', 1, f'Qual nome do meu {subject}?'),
        row(f'train-{i}-a', f'train-{i}', 2, f'Meu {subject} se chama {name}.'))]
    rival = row('isolated-rival', 'isolated-rival', 1, 'Meu drone se chama Boreal.')
    blocked = [dict(r, source_kind='assistant_generated') if r['source_id']=='train-2-a' else r
               for r in training]
    competing = [r for i, (subject, color) in enumerate(zip(subjects, ('branco', 'preto', 'verde')))
                 for r in (row(f'color-{i}-q', f'color-{i}', 1, f'Qual nome do meu {subject}?'),
                           row(f'color-{i}-a', f'color-{i}', 2, f'Meu {subject} é {color}.'))]
    return [('no_scaffold', isolated), ('observed_scaffold', isolated+training),
            ('isolated_conflict', isolated+training+[rival]),
            ('assistant_barrier', isolated+blocked),
            ('competing_frames', isolated+training+competing)]


def descriptors(stage):
    known = ('Meu drone se chama Auri.',)
    if stage == 'isolated_conflict':
        known += ('Meu drone se chama Boreal.',)
    if stage == 'competing_frames':
        known += ('Meu drone é azul.',)
    kind = 'conflict' if len(known)>1 else 'answer'
    return [('known', 'Qual nome do meu drone?', kind, known),
            ('new_prefix', 'Lembre: Qual nome do meu drone?', kind, known),
            ('other_subject', 'Qual nome do meu robô?', 'answer', ('Meu robô se chama Lumo.',)),
            ('changed_relation', 'Qual potência do meu drone?', 'absence', ()),
            ('unknown_subject', 'Qual nome do meu trem?', 'absence', ()),
            ('unrelated', 'Temperatura em Marte?', 'absence', ()),
            ('two_cues', 'Qual nome do meu drone? Qual nome do meu robô?', 'absence', ())]


def evaluate(stage, rows, adapter, renamed=False):
    memory, provenance = adapt(rows, adapter)
    transform = lambda xs: tuple(10000-x for x in xs) if renamed else xs
    if renamed:
        state = memory.snapshot()
        copied = TrajectoryGenerationExperiment()
        renamed_provenance = {}
        for r in state['observations']:
            receipt = copied.observe(transform(memory.expand(r['payload_id'])), observation_id=r['observation_id'],
                                     hierarchy_id=r['hierarchy_id'], stream_id=r['stream_id'])
            renamed_provenance[receipt.payload_id] = provenance[r['payload_id']]
        provenance = renamed_provenance
        memory = copied
    cases = []
    for name, query, kind, expected in descriptors(stage):
        query_symbols = transform(encode(query, adapter))
        result = checked_read(memory, query_symbols)
        targets = {transform(encode(t, adapter)) for t in expected}
        outputs = {c['output'] for c in result['candidates']}
        witness_ids = {x for c in result['candidates'] for s, t, _ in c['witnesses'] for x in (s,t)}
        witness_ids.update(c['payload_id'] for c in result['candidates'])
        assert witness_ids <= set(provenance), 'unaddressable frame witness'
        correct = kind=='answer' and result['hypothesis'] in targets
        passed = correct if kind=='answer' else not outputs if kind=='absence' else (
            targets==outputs and result['hypothesis'] is None)
        cases.append(dict(name=name, kind=kind, query=query_symbols, expected=tuple(sorted(targets)),
            quality_pass=passed, correct_answer=correct,
            false_unique=result['hypothesis'] is not None and result['hypothesis'] not in targets,
            result=result, cold_parity=True, generation_unchanged=True,
            learning_unchanged=True, witnesses_addressable=True))
    return dict(adapter=adapter, renamed=renamed, cases=cases,
                root_provenance=tuple(dict(payload_id=root,native_addresses=tuple(origins))
                                      for root,origins in sorted(provenance.items())),
                quality_status='PASS' if all(c['quality_pass'] for c in cases) else 'FAIL')


def probe(library=None):
    stages = []
    for stage, rows in fixtures():
        native_parity = None
        inputs = rows
        if library:
            with tempfile.TemporaryDirectory(prefix='frame-native-') as directory:
                native = NativeProbe(library, Path(directory))
                try:
                    for row in rows:
                        status, receipt = native.call('observe_structural_text', row)
                        assert status==0 and not receipt['duplicate']
                    warm = collect(native, rows)
                    native.reopen()
                    cold = collect(native, rows)
                    assert warm==cold
                    inputs=cold
                    native_parity=True
                finally:
                    native.close()
        evaluations = [evaluate(stage, inputs, adapter, renamed) for adapter in ('unicode','utf8')
                       for renamed in (False,True)]
        if library:
            assert evaluations == [evaluate(stage, rows, adapter, renamed)
                                   for adapter in ('unicode','utf8') for renamed in (False,True)]
        stages.append(dict(stage=stage, observations=len(rows), native_cold_parity=native_parity,
                           evaluations=evaluations))
    cases = [c for s in stages for a in s['evaluations'] for c in a['cases']]
    counts = dict(cases=len(cases), passed=sum(c['quality_pass'] for c in cases),
                  correct_answers=sum(c['correct_answer'] for c in cases),
                  answer_cases=sum(c['kind']=='answer' for c in cases),
                  false_unique=sum(c['false_unique'] for c in cases),
                  absence_empty=sum(c['kind']=='absence' and not c['result']['candidates'] for c in cases),
                  conflicts_preserved=sum(c['kind']=='conflict' and c['quality_pass'] for c in cases))
    return dict(format='memoria.ia-frame-analogy-v1', integrity_status='PASS',
        quality_status='PASS' if counts['cases']==counts['passed'] else 'FAIL',
        policy_status='EXPERIMENTAL_DIAGNOSTIC', engine_changed=False, native_changed=False,
        native_executed=library is not None, prior_bridge_score_changed=False,
        counts=counts, stages=stages)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', type=Path)
    parser.add_argument('--strict-quality', action='store_true')
    args = parser.parse_args()
    report = probe(args.library)
    print(json.dumps(report, ensure_ascii=False, separators=(',',':')))
    raise SystemExit(1 if args.strict_quality and report['quality_status']!='PASS' else 0)
