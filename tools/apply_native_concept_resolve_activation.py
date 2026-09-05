from pathlib import Path

# Native resolver: miss-only concept rewrite/retry, separate concept namespace.
p = Path('native/mobile/memoria_mobile.c')
s = p.read_text()
old = '#include "concept_runtime_state.h"\n'
new = '#include "concept_runtime_state.h"\n#include "concept_query_rewrite.h"\n'
if s.count(old) != 1:
    raise SystemExit('concept include anchor mismatch')
s = s.replace(old, new, 1)

start = s.index('memoria_mobile_status memoria_mobile_resolve_context_json(')
end = s.index('memoria_mobile_status memoria_mobile_store_episode_json(', start)
fn = s[start:end]
old_decl = '    char *json, *query, *namespace_id, *ctx, *st, *root, *created_time;\n'
new_decl = '    char *json, *query, *namespace_id, *concept_namespace, *ctx, *st, *root, *created_time;\n'
if fn.count(old_decl) != 1:
    raise SystemExit('resolve declaration anchor mismatch')
fn = fn.replace(old_decl, new_decl, 1)
old_decl2 = '    int trajectory_mode;\n'
new_decl2 = '    int trajectory_mode, concept_retry_used = 0;\n'
if fn.count(old_decl2) != 1:
    raise SystemExit('resolve trajectory declaration anchor mismatch')
fn = fn.replace(old_decl2, new_decl2, 1)
old_parse = '''    query = json_string(json, "query");\n    namespace_id = json_string(json, "namespace");\n    if (!namespace_id) namespace_id = dup_string("");\n    if (!query || !namespace_id) { free(query); free(namespace_id); free(json); return MEMORIA_MOBILE_INVALID_ARGUMENT; }\n'''
new_parse = '''    query = json_string(json, "query");\n    namespace_id = json_string(json, "namespace");\n    concept_namespace = json_string(json, "concept_namespace");\n    if (!namespace_id) namespace_id = dup_string("");\n    if (!concept_namespace) concept_namespace = dup_string("");\n    if (!query || !namespace_id || !concept_namespace) {\n        free(query); free(namespace_id); free(concept_namespace); free(json);\n        return MEMORIA_MOBILE_INVALID_ARGUMENT;\n    }\n'''
if fn.count(old_parse) != 1:
    raise SystemExit('resolve parse anchor mismatch')
fn = fn.replace(old_parse, new_parse, 1)

# Add one retry helper call site before the attempt loop.
source_anchor = '''        ++source_count;\n    }\n    if (try_temporal_response(h, query, namespace_id, NULL, out, &response_status)) {\n'''
source_new = '''        ++source_count;\n    }\nresolve_attempt:\n    if (try_temporal_response(h, query, namespace_id, NULL, out, &response_status)) {\n'''
if fn.count(source_anchor) != 1:
    raise SystemExit('resolve attempt label anchor mismatch')
fn = fn.replace(source_anchor, source_new, 1)

# Genuine trajectory miss: retry once through concept canonicalization.
old = '''        if (!tr.hit) {\n            free(namespace_id); free(query); free(json);\n            return unresolved(out, "no justified active trajectory source");\n        }\n'''
new = '''        if (!tr.hit) {\n            memoria_concept_rewrite_result rewrite;\n            if (!concept_retry_used && concept_namespace[0]) {\n                rewrite = memoria_concept_rewrite_query(\n                    memoria_concept_runtime_index(h->concept_runtime), concept_namespace, query, 6u\n                );\n                if (rewrite.status == MEMORIA_CONCEPT_REWRITE_REWRITTEN &&\n                    rewrite.rewritten_query[0] && strcmp(rewrite.rewritten_query, query) != 0) {\n                    char *retry_query = dup_string(rewrite.rewritten_query);\n                    if (!retry_query) {\n                        free(namespace_id); free(concept_namespace); free(query); free(json);\n                        return MEMORIA_MOBILE_INTERNAL_ERROR;\n                    }\n                    free(query);\n                    query = retry_query;\n                    concept_retry_used = 1;\n                    goto resolve_attempt;\n                }\n            }\n            free(namespace_id); free(concept_namespace); free(query); free(json);\n            return unresolved(out, "no justified active trajectory source");\n        }\n'''
if fn.count(old) != 1:
    raise SystemExit('trajectory miss anchor mismatch')
fn = fn.replace(old, new, 1)

# Genuine semantic miss: same one-shot retry.
old = '''    if (!r.hit) {\n        free(namespace_id); free(query); free(json);\n        return unresolved(out, "no justified native semantic source");\n    }\n'''
new = '''    if (!r.hit) {\n        memoria_concept_rewrite_result rewrite;\n        if (!concept_retry_used && concept_namespace[0]) {\n            rewrite = memoria_concept_rewrite_query(\n                memoria_concept_runtime_index(h->concept_runtime), concept_namespace, query, 6u\n            );\n            if (rewrite.status == MEMORIA_CONCEPT_REWRITE_REWRITTEN &&\n                rewrite.rewritten_query[0] && strcmp(rewrite.rewritten_query, query) != 0) {\n                char *retry_query = dup_string(rewrite.rewritten_query);\n                if (!retry_query) {\n                    free(namespace_id); free(concept_namespace); free(query); free(json);\n                    return MEMORIA_MOBILE_INTERNAL_ERROR;\n                }\n                free(query);\n                query = retry_query;\n                concept_retry_used = 1;\n                goto resolve_attempt;\n            }\n        }\n        free(namespace_id); free(concept_namespace); free(query); free(json);\n        return unresolved(out, "no justified native semantic source");\n    }\n'''
if fn.count(old) != 1:
    raise SystemExit('semantic miss anchor mismatch')
fn = fn.replace(old, new, 1)

# Every resolver exit after parsing must release concept_namespace too.
fn = fn.replace('free(namespace_id); free(query); free(json);', 'free(namespace_id); free(concept_namespace); free(query); free(json);')
fn = fn.replace('free(query); free(namespace_id); free(json);', 'free(query); free(namespace_id); free(concept_namespace); free(json);')
# Avoid accidental double insertion in the two new blocks above.
fn = fn.replace('free(namespace_id); free(concept_namespace); free(concept_namespace); free(query); free(json);', 'free(namespace_id); free(concept_namespace); free(query); free(json);')
fn = fn.replace('free(query); free(namespace_id); free(concept_namespace); free(concept_namespace); free(json);', 'free(query); free(namespace_id); free(concept_namespace); free(json);')

s = s[:start] + fn + s[end:]
p.write_text(s)

# NativeConversationService transports concept namespace independently.
p = Path('src/memoria_resolutiva/native_conversation.py')
s = p.read_text()
old = '''        organization_id: str,\n        runtime_manager: NativeRuntimeManager | None = None,\n    ) -> None:\n'''
new = '''        organization_id: str,\n        concept_namespace: str | None = None,\n        runtime_manager: NativeRuntimeManager | None = None,\n    ) -> None:\n'''
if s.count(old) != 1:
    raise SystemExit('native conversation constructor anchor mismatch')
s = s.replace(old, new, 1)
old = '        self.organization_id = organization_id\n'
new = '        self.organization_id = organization_id\n        self.concept_namespace = concept_namespace\n'
if s.count(old) != 1:
    raise SystemExit('native conversation org anchor mismatch')
s = s.replace(old, new, 1)
old = '''            {"query": query, "namespace": session_id or ""},\n'''
new = '''            {\n                "query": query,\n                "namespace": session_id or "",\n                "concept_namespace": self.concept_namespace or "",\n            },\n'''
if s.count(old) != 1:
    raise SystemExit('native conversation resolve payload anchor mismatch')
p.write_text(s.replace(old, new, 1))

# Product server resolves concept namespace before native backend construction and advertises activation.
p = Path('src/memoria_resolutiva/product_server.py')
s = p.read_text()
old = 'def _build_conversation_service(*, evidence_service: ProductEvidenceService, data_dir: Path, organization_id: str, native_data_dir: Path | None = None):\n'
new = 'def _build_conversation_service(*, evidence_service: ProductEvidenceService, data_dir: Path, organization_id: str, concept_namespace: str | None, native_data_dir: Path | None = None):\n'
if s.count(old) != 1:
    raise SystemExit('build conversation signature mismatch')
s = s.replace(old, new, 1)
old = '''        organization_id=organization_id,\n    )\n\n\ndef _build_episodic_service'''
new = '''        organization_id=organization_id,\n        concept_namespace=concept_namespace,\n    )\n\n\ndef _build_episodic_service'''
if s.count(old) != 1:
    raise SystemExit('native conversation construction anchor mismatch')
s = s.replace(old, new, 1)
old = '''    evidence_service = ProductEvidenceService.open(data_dir / "evidence", backend=storage_backend, allow_fallback=storage_allow_fallback)\n    native_shared_data_dir = _native_shared_data_dir(data_dir)\n    conversation_backend = _build_conversation_service(\n'''
new = '''    concept_namespace = os.getenv("MEMORIA_CONCEPT_NAMESPACE", "semantic").strip() or None\n    evidence_service = ProductEvidenceService.open(data_dir / "evidence", backend=storage_backend, allow_fallback=storage_allow_fallback)\n    native_shared_data_dir = _native_shared_data_dir(data_dir)\n    conversation_backend = _build_conversation_service(\n'''
if s.count(old) != 1:
    raise SystemExit('product server evidence anchor mismatch')
s = s.replace(old, new, 1)
old = '''        organization_id=organization_id,\n        native_data_dir=native_shared_data_dir,\n    )\n    episodic_service = _build_episodic_service(\n'''
new = '''        organization_id=organization_id,\n        concept_namespace=concept_namespace,\n        native_data_dir=native_shared_data_dir,\n    )\n    episodic_service = _build_episodic_service(\n'''
if s.count(old) != 1:
    raise SystemExit('product server conversation call anchor mismatch')
s = s.replace(old, new, 1)
old = '    concept_namespace = os.getenv("MEMORIA_CONCEPT_NAMESPACE", "semantic").strip() or None\n    concept_scope = MemoryScope(organization_id)\n'
new = '    concept_scope = MemoryScope(organization_id)\n'
if s.count(old) != 1:
    raise SystemExit('duplicate concept namespace anchor mismatch')
s = s.replace(old, new, 1)
old = '    automatic_concept_resolution = False\n'
new = '    automatic_concept_resolution = conversation_is_native and native_concept_catalog_materialized\n'
if s.count(old) != 1:
    raise SystemExit('automatic concept resolution anchor mismatch')
p.write_text(s.replace(old, new, 1))

# Host end-to-end test: no concept namespace => miss; explicit concept namespace => canonical retry hit.
Path('native/mobile/tests/concept_resolve_activation.c').write_text(r'''#include "memoria_mobile.h"

#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static memoria_mobile_status call_json(
    memoria_mobile_status (*fn)(memoria_mobile_handle *, memoria_mobile_buffer, memoria_mobile_buffer *),
    memoria_mobile_handle *h,
    const char *json,
    char *out_text,
    size_t out_cap
) {
    memoria_mobile_buffer req = {(const uint8_t *)json, strlen(json)};
    memoria_mobile_buffer out = {0};
    memoria_mobile_status st = fn(h, req, &out);
    if (out_text && out_cap) {
        size_t n = out.size < out_cap - 1u ? out.size : out_cap - 1u;
        if (out.data && n) memcpy(out_text, out.data, n);
        out_text[n] = 0;
    }
    if (out.data) memoria_mobile_free_buffer(out);
    return st;
}

int main(void) {
    char path[256], response[4096];
    memoria_mobile_handle *h = NULL;
    snprintf(path, sizeof(path), "/tmp/memoria-concept-resolve-%ld", (long)getpid());
    {
        char command[320];
        snprintf(command, sizeof(command), "rm -rf %s", path);
        (void)system(command);
    }
    assert(memoria_mobile_open(path, "org-concept-resolve", &h) == MEMORIA_MOBILE_OK);

    assert(call_json(
        memoria_mobile_apply_concept_catalog_json, h,
        "{\"schema\":1,\"namespace\":\"semantic\","
        "\"fingerprint\":\"sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc\","
        "\"concept_count\":1,\"rows\":[\"15:concept:voltage8:semantic7:voltage8:electric2:7:voltage3:ddp1:7:circuit\"]}",
        response, sizeof(response)
    ) == MEMORIA_MOBILE_OK);
    assert(strstr(response, "\"status\":\"OK\"") != NULL);

    assert(call_json(
        memoria_mobile_learn_turn_json, h,
        "{\"role\":\"user\",\"text\":\"voltage\",\"memory_id\":\"m-voltage\","
        "\"namespace\":\"session-a\",\"source_type\":\"user_assertion\",\"source_authority\":1.0}",
        response, sizeof(response)
    ) == MEMORIA_MOBILE_OK);

    assert(call_json(
        memoria_mobile_resolve_context_json, h,
        "{\"query\":\"ddp\",\"namespace\":\"session-a\"}",
        response, sizeof(response)
    ) == MEMORIA_MOBILE_UNRESOLVED);
    assert(strstr(response, "\"status\":\"UNRESOLVED\"") != NULL);

    assert(call_json(
        memoria_mobile_resolve_context_json, h,
        "{\"query\":\"ddp\",\"namespace\":\"session-a\",\"concept_namespace\":\"semantic\"}",
        response, sizeof(response)
    ) == MEMORIA_MOBILE_OK);
    assert(strstr(response, "\"status\":\"HIT\"") != NULL);
    assert(strstr(response, "voltage") != NULL);

    memoria_mobile_close(h);
    return 0;
}
''')

p = Path('native/mobile/CMakeLists.txt')
s = p.read_text()
anchor = '''  add_executable(memoria_concept_query_rewrite_test tests/concept_query_rewrite.c)\n  target_link_libraries(memoria_concept_query_rewrite_test PRIVATE memoria_concept_internal)\n  target_include_directories(memoria_concept_query_rewrite_test PRIVATE ${CMAKE_CURRENT_LIST_DIR})\n  set_target_properties(memoria_concept_query_rewrite_test PROPERTIES C_STANDARD 11 C_STANDARD_REQUIRED YES)\n  add_test(NAME memoria_concept_query_rewrite_test COMMAND memoria_concept_query_rewrite_test)\n\n'''
addition = '''  add_executable(memoria_concept_resolve_activation_test tests/concept_resolve_activation.c)\n  target_link_libraries(memoria_concept_resolve_activation_test PRIVATE memoria_mobile)\n  target_include_directories(memoria_concept_resolve_activation_test PRIVATE ${CMAKE_CURRENT_LIST_DIR}/../../include ${CMAKE_CURRENT_LIST_DIR})\n  set_target_properties(memoria_concept_resolve_activation_test PROPERTIES C_STANDARD 11 C_STANDARD_REQUIRED YES)\n  add_test(NAME memoria_concept_resolve_activation_test COMMAND memoria_concept_resolve_activation_test)\n\n'''
if s.count(anchor) != 1:
    raise SystemExit('CMake concept rewrite anchor mismatch')
p.write_text(s.replace(anchor, anchor + addition, 1))

# Python boundary proves separate concept namespace is transported.
Path('tests/test_native_conversation_concept_namespace.py').write_text('''from __future__ import annotations\n\nfrom memoria_resolutiva.native_conversation import NativeConversationService\n\n\nclass _Lease:\n    def __init__(self):\n        self.calls = []\n\n    def call(self, name: str, payload: dict[str, object]):\n        self.calls.append((name, payload))\n        return 2, {"status": "UNRESOLVED"}\n\n    def release(self):\n        pass\n\n\nclass _Manager:\n    def __init__(self):\n        self.lease = _Lease()\n\n    def acquire(self, **_kwargs):\n        return self.lease\n\n\ndef test_native_resolve_transports_concept_namespace_separately(tmp_path):\n    manager = _Manager()\n    service = NativeConversationService(\n        library_path=tmp_path / "unused.so",\n        data_dir=tmp_path / "native",\n        organization_id="org-a",\n        concept_namespace="semantic",\n        runtime_manager=manager,\n    )\n    result = service.resolve(query="ddp", session_id="session-a")\n    assert result.status == "UNRESOLVED"\n    assert manager.lease.calls == [\n        (\n            "memoria_mobile_resolve_context_json",\n            {"query": "ddp", "namespace": "session-a", "concept_namespace": "semantic"},\n        )\n    ]\n''')
