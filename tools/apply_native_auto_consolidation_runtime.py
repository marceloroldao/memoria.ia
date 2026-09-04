from pathlib import Path
p = Path('native/mobile/memoria_mobile.c')
s = p.read_text()

include_anchor = '#include "lineage_state.h"\n'
includes = '#include "semantic_consolidation_state.h"\n#include "semantic_consolidation_request.h"\n'
if '#include "semantic_consolidation_state.h"' not in s:
    s = s.replace(include_anchor, include_anchor + includes, 1)

anchor = 'uint32_t memoria_mobile_abi_version(void) { return MEMORIA_MOBILE_ABI_VERSION; }\n'
helper = r'''
static int source_triggers_semantic_consolidation(const char *source_type) {
    if (!source_type) return 0;
    return strcmp(source_type, "user_assertion") == 0 ||
           strcmp(source_type, "user_correction") == 0 ||
           strcmp(source_type, "direct_observation") == 0 ||
           strcmp(source_type, "external_import") == 0;
}

static void maybe_auto_semantic_consolidate(memoria_mobile_handle *h, const turn_row *trigger) {
    memoria_semantic_candidate candidates[8];
    size_t count, i;
    if (!h || !trigger || !source_triggers_semantic_consolidation(trigger->source_type) || trigger->relation_count == 0)
        return;
    memset(candidates, 0, sizeof(candidates));
    count = memoria_semantic_consolidation_from_turns(h->turns, h->turn_count, 2, candidates, 8);
    for (i = 0; i < count; ++i) {
        char request_json[8192];
        memoria_mobile_buffer req;
        memoria_mobile_buffer derived_out = {0};
        if (!memoria_semantic_consolidation_request_json(
                &candidates[i], (long)h->turn_count + 1, request_json, sizeof(request_json)))
            continue;
        req.data = (const uint8_t *)request_json;
        req.size = strlen(request_json);
        (void)memoria_mobile_learn_turn_json(h, req, &derived_out);
        if (derived_out.data) memoria_mobile_free_buffer(derived_out);
    }
}

'''
if 'static void maybe_auto_semantic_consolidate' not in s:
    if anchor not in s:
        raise SystemExit('ABI anchor not found')
    s = s.replace(anchor, helper + anchor, 1)

hook_anchor = '    h->sequence = next_sequence;\n    response_status = set_responsef(out, MEMORIA_MOBILE_OK,\n'
replacement = '    h->sequence = next_sequence;\n    maybe_auto_semantic_consolidate(h, &h->turns[h->turn_count - 1u]);\n    response_status = set_responsef(out, MEMORIA_MOBILE_OK,\n'
if 'maybe_auto_semantic_consolidate(h, &h->turns[h->turn_count - 1u]);' not in s:
    if hook_anchor not in s:
        raise SystemExit('learn hook anchor not found')
    s = s.replace(hook_anchor, replacement, 1)

p.write_text(s)
