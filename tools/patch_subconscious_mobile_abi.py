from pathlib import Path

# 1) Strong HITs are not knowledge gaps.
p = Path('native/mobile/subconscious_mobile.c')
s = p.read_text(encoding='utf-8')
old = '''    if (resolved && response_json.data && response_json.size) {\n        resolved_response = buffer_string(response_json);\n        if (resolved_response) confidence = json_double_value(resolved_response, "confidence", 0.0);\n        free(resolved_response);\n    }\n    slot = runtime_for(handle, 1);\n'''
new = '''    if (resolved && response_json.data && response_json.size) {\n        resolved_response = buffer_string(response_json);\n        if (resolved_response) confidence = json_double_value(resolved_response, "confidence", 0.0);\n        free(resolved_response);\n    }\n    if (resolved && confidence >= 0.75) { free(query); return; }\n    slot = runtime_for(handle, 1);\n'''
if old not in s: raise SystemExit('mobile confidence anchor not found')
p.write_text(s.replace(old, new, 1), encoding='utf-8')

# 2) Wrap resolve and close while keeping frozen v1 implementation unchanged.
p = Path('native/mobile/memoria_mobile_post_v1.c')
s = p.read_text(encoding='utf-8')
old = '''#define memoria_mobile_resolve_context_json memoria_mobile_resolve_context_json_v1_core\n#include "memoria_mobile.c"\n#undef memoria_mobile_resolve_context_json\n'''
new = '''#define memoria_mobile_resolve_context_json memoria_mobile_resolve_context_json_v1_core\n#define memoria_mobile_close memoria_mobile_close_v1_core\n#include "memoria_mobile.c"\n#undef memoria_mobile_close\n#undef memoria_mobile_resolve_context_json\n#include "subconscious_mobile.h"\n'''
if old not in s: raise SystemExit('post-v1 wrapper anchor not found')
s = s.replace(old, new, 1)
old = '''    status = memoria_mobile_resolve_context_json_v1_core(h, req, &core);\n    if (status != MEMORIA_MOBILE_OK || !core.data) {\n        if (core.data) {\n            memoria_mobile_status copied = set_response(out, (const char *)core.data, status);\n            memoria_mobile_free_buffer(core);\n            return copied;\n        }\n        return status;\n    }\n    status = external_enrich_resolve(h, req, core, out);\n    memoria_mobile_free_buffer(core);\n    return status;\n}\n'''
new = '''    status = memoria_mobile_resolve_context_json_v1_core(h, req, &core);\n    if (status != MEMORIA_MOBILE_OK || !core.data) {\n        memoria_subconscious_mobile_observe_resolution(h, req, status, core);\n        if (core.data) {\n            memoria_mobile_status copied = set_response(out, (const char *)core.data, status);\n            memoria_mobile_free_buffer(core);\n            return copied;\n        }\n        return status;\n    }\n    status = external_enrich_resolve(h, req, core, out);\n    memoria_subconscious_mobile_observe_resolution(h, req, status, *out);\n    memoria_mobile_free_buffer(core);\n    return status;\n}\n\nvoid memoria_mobile_close(memoria_mobile_handle *h) {\n    if (!h) return;\n    memoria_subconscious_mobile_forget_handle(h);\n    memoria_mobile_close_v1_core(h);\n}\n'''
if old not in s: raise SystemExit('resolve body anchor not found')
p.write_text(s.replace(old, new, 1), encoding='utf-8')

# 3) Build mobile adapter and its host test.
p = Path('native/mobile/CMakeLists.txt')
s = p.read_text(encoding='utf-8')
old = '''  semantic_kernel.c\n  subconscious_kernel.c\n  trajectory_kernel.c\n'''
new = '''  semantic_kernel.c\n  subconscious_kernel.c\n  subconscious_mobile.c\n  trajectory_kernel.c\n'''
if old not in s: raise SystemExit('cmake library anchor not found')
s = s.replace(old, new, 1)
old = '''  add_executable(memoria_subconscious_kernel_test tests/subconscious_kernel.c subconscious_kernel.c)\n  target_include_directories(memoria_subconscious_kernel_test PRIVATE ${CMAKE_CURRENT_LIST_DIR})\n  set_target_properties(memoria_subconscious_kernel_test PROPERTIES C_STANDARD 11 C_STANDARD_REQUIRED YES)\n  add_test(NAME memoria_subconscious_kernel_test COMMAND memoria_subconscious_kernel_test)\n\n'''
new = old + '''  add_executable(memoria_subconscious_mobile_test tests/subconscious_mobile.c subconscious_mobile.c subconscious_kernel.c)\n  target_include_directories(memoria_subconscious_mobile_test PRIVATE ${CMAKE_CURRENT_LIST_DIR} ${CMAKE_CURRENT_LIST_DIR}/../../include)\n  target_link_libraries(memoria_subconscious_mobile_test PRIVATE memoria_mobile)\n  set_target_properties(memoria_subconscious_mobile_test PROPERTIES C_STANDARD 11 C_STANDARD_REQUIRED YES)\n  add_test(NAME memoria_subconscious_mobile_test COMMAND memoria_subconscious_mobile_test)\n\n'''
if old not in s: raise SystemExit('cmake test anchor not found')
p.write_text(s.replace(old, new, 1), encoding='utf-8')
