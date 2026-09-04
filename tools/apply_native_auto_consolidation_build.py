from pathlib import Path

# Runtime hook
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
    if anchor not in s: raise SystemExit('runtime helper anchor missing')
    s = s.replace(anchor, helper + anchor, 1)
hook = '    h->sequence = next_sequence;\n    response_status = set_responsef(out, MEMORIA_MOBILE_OK,\n'
replacement = '    h->sequence = next_sequence;\n    maybe_auto_semantic_consolidate(h, &h->turns[h->turn_count - 1u]);\n    response_status = set_responsef(out, MEMORIA_MOBILE_OK,\n'
if 'maybe_auto_semantic_consolidate(h, &h->turns[h->turn_count - 1u]);' not in s:
    if hook not in s: raise SystemExit('runtime hook anchor missing')
    s = s.replace(hook, replacement, 1)
p.write_text(s)

# Build wiring
p = Path('native/mobile/CMakeLists.txt')
s = p.read_text()
source_anchor = '  semantic_consolidation_state.c\n'
if '  semantic_consolidation_request.c\n' not in s:
    if source_anchor not in s: raise SystemExit('source anchor missing')
    s = s.replace(source_anchor, source_anchor + '  semantic_consolidation_request.c\n', 1)

test_anchor = '  add_executable(memoria_mobile_memory_space tests/memory_space.c)\n'
test_block = '''  add_executable(memoria_mobile_automatic_semantic_consolidation tests/automatic_semantic_consolidation_mobile.c)\n  target_link_libraries(memoria_mobile_automatic_semantic_consolidation PRIVATE memoria_mobile)\n  target_include_directories(memoria_mobile_automatic_semantic_consolidation PRIVATE ${CMAKE_CURRENT_LIST_DIR}/../../include ${CMAKE_CURRENT_LIST_DIR})\n  add_test(NAME memoria_mobile_automatic_semantic_consolidation COMMAND memoria_mobile_automatic_semantic_consolidation)\n\n'''
if 'memoria_mobile_automatic_semantic_consolidation' not in s:
    if test_anchor not in s: raise SystemExit('test anchor missing')
    s = s.replace(test_anchor, test_block + test_anchor, 1)
p.write_text(s)
