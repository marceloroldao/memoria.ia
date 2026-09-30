#!/usr/bin/env python3
"""Source/target contrast with an offline veto and positive transfer controls."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from random import Random

from trajectory_response_quality_probe import (
    TrajectoryGenerationExperiment, encode, evaluate_case, fixture_groups,
)


def contrast_for_generation(memory, query, generated):
    contrast = memory.temporal_nodule_contrast(query)
    if contrast.recall.selected is not None:
        expanded = memory.temporal_nodule_contrast(query, include_shorter=True)
        if expanded.recall.ambiguous or expanded.recall.truncated:
            contrast = expanded
    if generated.association_evidence is not None:
        assert asdict(contrast.recall) == asdict(generated.association_evidence)
    return contrast


def proposed_veto(generated, contrast):
    """No labels: test only unique nodule routes with solely carried targets."""
    if generated.mode != 'NODULE_RECALL' or generated.selected is None:
        return False
    matching = [c for c in contrast.candidates if c.symbols == generated.selected]
    return bool(matching and all(c.carried_pairs and not c.introduced_pairs for c in matching))


def check_read(memory, query):
    before = memory.snapshot(), memory.learning_state()
    generated = memory.generate(query)
    contrast = contrast_for_generation(memory, query, generated)
    reopened = TrajectoryGenerationExperiment.restore(memory.snapshot())
    cold = reopened.generate(query)
    assert asdict(generated) == asdict(cold)
    assert asdict(contrast) == asdict(contrast_for_generation(reopened, query, cold))
    veto = proposed_veto(generated, contrast)
    assert asdict(memory.generate(query)) == asdict(generated), 'diagnostic changed selection'
    assert (memory.snapshot(), memory.learning_state()) == before, 'query learned'
    return generated, contrast, veto


def controls():
    rows = []
    for kind, present in [('introduced', (False, False)), ('carried', (True, True)),
                          ('mixed', (True, False))]:
        for renamed in (False, True):
            for padding in (1, 4, 8, 16):
                transform = lambda xs: tuple(x * 101 + 17 if renamed else x for x in xs)
                memory = TrajectoryGenerationExperiment()
                for i, carried in enumerate(present):
                    source = (90 + 2*i,) + ((7, 8, 9) if carried else ()) + (1, 2, 3, 91 + 2*i)
                    destination = (94 + 2*i, 7, 8, 9, 95 + 2*i)
                    memory.observe(transform(source), observation_id=f'{i}:source', stream_id=str(i))
                    memory.observe(transform(destination), observation_id=f'{i}:target', stream_id=str(i))
                query = transform((100,) * padding + (1, 2, 3) + (101,) * padding)
                generated, contrast, veto = check_read(memory, query)
                assert generated.mode == 'NODULE_RECALL' and generated.selected == transform((7, 8, 9))
                candidate = contrast.candidates[0]
                assert candidate.carried_pairs == sum(present)
                assert candidate.introduced_pairs == 2 - sum(present)
                assert veto == (kind == 'carried')
                rows.append(dict(kind=kind, renamed=renamed, padding=padding,
                                 query=query, selected=generated.selected,
                                 introduced_pairs=candidate.introduced_pairs,
                                 carried_pairs=candidate.carried_pairs, veto=veto))
    return rows


def probe(seed):
    rng = Random(seed)
    rows = []
    for trial in range(2):
        groups = fixture_groups(rng)
        for adapter in ('unicode', 'utf8'):
            for group, records, descriptors in groups:
                memory = TrajectoryGenerationExperiment()
                for i, (text, stream) in enumerate(records):
                    memory.observe(encode(text, adapter), observation_id=str(i), stream_id=stream)
                reopened = TrajectoryGenerationExperiment.restore(memory.snapshot())
                for descriptor in descriptors:
                    row = evaluate_case(memory, reopened, descriptor, adapter)
                    generated, contrast, veto = check_read(memory, encode(descriptor['query'], adapter))
                    row.update(trial=trial, group=group, veto=veto,
                               contrast=[dict(**asdict(c), introduced_pairs=c.introduced_pairs,
                                              carried_pairs=c.carried_pairs) for c in contrast.candidates],
                               contrast_truncated=contrast.recall.truncated,
                               contrast_ambiguous=contrast.recall.ambiguous)
                    rows.append(row)
    positive = controls()
    counts = dict(
        baseline_correct_unique_answers=sum(r['selected_correct'] for r in rows),
        counterfactual_correct_unique_answers=sum(r['selected_correct'] and not r['veto'] for r in rows),
        baseline_false_unique=sum(r['false_unique'] for r in rows),
        counterfactual_false_unique=sum(r['false_unique'] and not r['veto'] for r in rows),
        baseline_absence_false_unique=sum(r['kind'] == 'absence' and r['false_unique'] for r in rows),
        counterfactual_absence_false_unique=sum(r['kind'] == 'absence' and r['false_unique'] and not r['veto'] for r in rows),
        valid_transfer_controls=len(positive),
        lost_valid_transfers=sum(r['veto'] for r in positive),
    )
    return dict(format='memoria.ia-temporal-transition-contrast-v1', seed=seed,
                integrity_status='PASS', quality_status='UNRESOLVED',
                selection_policy_changed=False, veto_adopted=False,
                counts=counts, positive_controls=positive, cases=rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--seed', type=int, default=20260930)
    options = parser.parse_args()
    print(json.dumps(probe(options.seed), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
