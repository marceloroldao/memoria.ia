from pathlib import Path

path = Path('native/mobile/memoria_mobile.c')
text = path.read_text()

include_anchor = '#include "memory_space.h"\n'
if '#include "lineage_state.h"' not in text:
    text = text.replace(include_anchor, include_anchor + '#include "lineage_state.h"\n', 1)

start_marker = 'static int active_lineage_root(memoria_mobile_handle *h, const char *memory_id, const char *namespace_id, lineage_root *out) {'
start = text.index(start_marker)
pos = start
brace = 0
seen_open = False
while pos < len(text):
    ch = text[pos]
    if ch == '{':
        brace += 1
        seen_open = True
    elif ch == '}':
        brace -= 1
        if seen_open and brace == 0:
            end = pos + 1
            break
    pos += 1
else:
    raise RuntimeError('active_lineage_root end not found')

replacement = '''static int active_lineage_root(memoria_mobile_handle *h, const char *memory_id, const char *namespace_id, lineage_root *out) {
    memoria_lineage_result result = {0};
    turn_row *root;
    if (!h || !memory_id || !*memory_id || !out) return 0;
    if (!memoria_lineage_rows_resolve(h->turns, h->turn_count, memory_id, namespace_id, &result)) return 0;
    if (!result.factual_active || !result.representative_root_id) return 0;
    root = find_turn_in_namespace(h, result.representative_root_id, namespace_id);
    if (!root || root->superseded || root->superseded_by[0]) return 0;
    out->memory_id = root->memory_id;
    out->source_type = root->source_type;
    out->authority = root->authority;
    out->order = root->order;
    out->created_time = root->created_time;
    return 1;
}'''

text = text[:start] + replacement + text[end:]
path.write_text(text)
