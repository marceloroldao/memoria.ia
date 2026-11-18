#!/usr/bin/env python3
"""Read-only diagnosis and rejected coverage-threshold ablation, not a policy."""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
import json
from random import Random

from trajectory_response_quality_probe import (
    TrajectoryGenerationExperiment, encode, evaluate_case, fixture_groups,
)


THRESHOLDS = (0.0, 0.25, 0.5, 0.75, 1.0)


def longest_shared_span(left, right):
    """Length of a contiguous ordered match; disjoint matches never add up."""
    previous = [0] * (len(right) + 1)
    longest = 0
    for item in left:
        current = [0] * (len(right) + 1)
        for j, other in enumerate(right, 1):
            if item == other:
                current[j] = previous[j - 1] + 1
                longest = max(longest, current[j])
        previous = current
    return longest


def diagnose(memory, query, result):
    evidence = result.association_evidence
    rows = []
    for candidate in (() if evidence is None else evidence.candidates):
        witnesses = []
        for source, target, stream in candidate.witnesses:
            source_symbols = memory.expand(source)
            span = longest_shared_span(query, source_symbols)
            witnesses.append(dict(source=source, target=target, stream=stream,
                                  shared_span=span, full_query=span == len(query)))
        rows.append(dict(symbols=candidate.symbols, source_width=candidate.source_width,
                         primary_cue_coverage=candidate.source_width / len(query),
                         witnesses=witnesses))
    return rows


def proposed_veto(query, result, threshold):
    """Offline ablation: suspend ONLY unique nodule output below a ratio.

    No labels or language-specific information enter this proposed decision.
    It is deliberately not installed in the memory engine.
    """
    if result.mode != "NODULE_RECALL" or result.selected is None:
        return False
    candidates = result.association_evidence.candidates
    return max(candidate.source_width for candidate in candidates) / len(query) < threshold


def transfer_controls():
    rows = []
    payloads = ((90, 1, 2, 3, 91), (94, 7, 8, 9, 95),
                (92, 1, 2, 3, 93), (96, 7, 8, 9, 97))
    for renamed, padding in ((r, p) for r in (False, True) for p in (1, 4, 8, 16)):
        transform = lambda values: tuple(x * 101 + 17 if renamed else x for x in values)
        memory = TrajectoryGenerationExperiment()
        for i, values in enumerate(payloads):
            memory.observe(transform(values), observation_id=str(i))
        q = transform((100,) * padding + (1, 2, 3) + (101,) * padding)
        before = memory.snapshot(), memory.learning_state()
        result = memory.generate(q)
        assert result.mode == "NODULE_RECALL" and result.selected == transform((7, 8, 9))
        assert asdict(result) == asdict(TrajectoryGenerationExperiment.restore(memory.snapshot()).generate(q))
        diagnostics = diagnose(memory, q, result)
        assert (memory.snapshot(), memory.learning_state()) == before
        rows.append(dict(renamed=renamed, padding=padding, query=q, selected=result.selected,
                         diagnostics=diagnostics,
                         vetoes={str(t): proposed_veto(q, result, t) for t in THRESHOLDS}))
    assert all(rows[i]['vetoes'] == rows[i + 4]['vetoes'] for i in range(4)), \
        "symbol renaming changed threshold"
    return rows


def probe(seed, trials=2):
    rng = Random(seed)
    rows = []
    for trial in range(trials):
        groups = fixture_groups(rng)
        for adapter in ("unicode", "utf8"):
            for group, records, descriptors in groups:
                memory = TrajectoryGenerationExperiment()
                for i, (text, stream) in enumerate(records):
                    memory.observe(encode(text, adapter), observation_id=str(i), stream_id=stream)
                cold = TrajectoryGenerationExperiment.restore(memory.snapshot())
                for descriptor in descriptors:
                    row = evaluate_case(memory, cold, descriptor, adapter)
                    query = encode(descriptor['query'], adapter)
                    before = memory.snapshot(), memory.learning_state()
                    result = memory.generate(query)
                    diagnostics = diagnose(memory, query, result)
                    assert diagnostics == diagnose(cold, query, cold.generate(query))
                    assert (memory.snapshot(), memory.learning_state()) == before
                    row.update(group=group, trial=trial, diagnostics=diagnostics,
                               vetoes={str(t): proposed_veto(query, result, t) for t in THRESHOLDS})
                    rows.append(row)
    transfer = transfer_controls()
    sweep = []
    for threshold in THRESHOLDS:
        counts = Counter()
        for row in rows:
            veto = row['vetoes'][str(threshold)]
            counts['correct_unique_answers'] += row['selected_correct'] and not veto
            counts['false_unique_outputs'] += row['false_unique'] and not veto
            counts['absence_false_unique'] += row['kind'] == 'absence' and row['false_unique'] and not veto
            counts['suspended_selections'] += veto
        counts['lost_opaque_transfers'] = sum(row['vetoes'][str(threshold)] for row in transfer)
        sweep.append(dict(threshold=threshold, **counts))
    return dict(format='memoria.ia-query-specificity-ablation-v1', seed=seed,
                integrity_status='PASS', engine_policy_changed=False,
                quality_status='UNRESOLVED', threshold_sweep=sweep,
                opaque_transfer_controls=transfer, cases=rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--seed', type=int, default=20260930)
    options = parser.parse_args()
    print(json.dumps(probe(options.seed), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
