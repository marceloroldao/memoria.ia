"""Pure read-only trace shared by evaluation and local session diagnostics."""
from collections import Counter

from trajectory_analogy_frame_probe import middle, occurrences


def trace_transform(view, observations, query):
    """Explain already-learned frames, using no evaluator expected content."""
    raw = view['result']['raw_view']; symbols = tuple(map(ord, query))
    roots = sorted({row['text'] for row in observations if row.get('source_kind', 'user_turn') == 'user_turn'})
    traces = []; admitted = set()
    for frame in raw['frames']:
        if frame['route'] != 'symbol_transform':
            continue
        item = dict(frame_id=frame['frame_id'], witnesses=frame['witnesses'])
        starts = occurrences(tuple(frame['source_prefix']), symbols)
        item['source_prefix_occurrences'] = len(starts)
        if len(starts) != 1:
            item['status'] = 'SOURCE_PREFIX_COUNT'
        else:
            variable = middle(symbols[starts[0]:], tuple(frame['source_prefix']), tuple(frame['source_suffix']))
            item['variable'] = None if variable is None else ''.join(map(chr, variable))
            if variable is None:
                item['status'] = 'SOURCE_BOUNDARY'
            else:
                mapping = dict(frame['symbol_map'])
                item['unwitnessed_symbols'] = [dict(symbol=x, text=chr(x)) for x in sorted(set(variable)-set(mapping))]
                item['required_pairs'] = [dict(source=x, target=mapping.get(x)) for x in sorted(set(variable))]
                if item['unwitnessed_symbols']:
                    item['status'] = 'UNWITNESSED_QUERY_SYMBOLS'
                else:
                    converted = tuple(mapping[x] for x in variable)
                    head = tuple(frame['target_prefix']) + converted + tuple(frame['target_bridge'])
                    ending = tuple(frame['target_suffix'])
                    item.update(converted=''.join(map(chr, converted)), target_head=''.join(map(chr, head)),
                                target_suffix=''.join(map(chr, ending)), target_checks=[])
                    for text in roots:
                        payload = tuple(map(ord, text))
                        status = ('TARGET_PREFIX_MISMATCH' if payload[:len(head)] != head else
                                  'TARGET_SUFFIX_MISMATCH' if payload[-len(ending):] != ending else
                                  'EMPTY_VALUE_SLOT' if middle(payload, head, ending) is None else 'MATCH')
                        item['target_checks'].append(dict(text=text, status=status))
                        if status == 'MATCH': admitted.add(text)
                    item['status'] = ('ADMITTED_OBSERVED_ROOTS' if any(r['status'] == 'MATCH' for r in item['target_checks'])
                                      else 'NO_OBSERVED_TARGET_MATCH')
        traces.append(item)
    actual = sorted(c['text'] for c in raw['candidates']
                    if any(e['route'] == 'symbol_transform' for e in c['route_evidence']))
    return dict(format='memoria.ia-transform-admission-trace-v1', query=query, frames=traces,
                status_counts=dict(sorted(Counter(t['status'] for t in traces).items())),
                traced_candidate_texts=sorted(admitted), actual_candidate_texts=actual,
                candidate_set_equal=sorted(admitted) == actual,
                answer=None, qualified=False, selection_used=False)

