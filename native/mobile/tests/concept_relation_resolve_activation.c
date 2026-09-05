#include "memoria_mobile.h"

#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

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
    char path[256], response[8192];
    memoria_mobile_handle *h = NULL;
    snprintf(path, sizeof(path), "/tmp/memoria-concept-relation-resolve-%ld", (long)getpid());
    {
        char command[320];
        snprintf(command, sizeof(command), "rm -rf %s", path);
        (void)system(command);
    }
    assert(memoria_mobile_open(path, "org-concept-relation-resolve", &h) == MEMORIA_MOBILE_OK);

    assert(call_json(
        memoria_mobile_apply_concept_catalog_json, h,
        "{\"schema\":1,\"namespace\":\"semantic\","
        "\"fingerprint\":\"sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd\","
        "\"concept_count\":1,\"rows\":[\"7:voltage8:semantic7:voltage8:electric2:7:voltage3:ddp0:\"]}",
        response, sizeof(response)
    ) == MEMORIA_MOBILE_OK);

    assert(call_json(
        memoria_mobile_learn_turn_json, h,
        "{\"role\":\"user\",\"text\":\"charger is voltage\",\"memory_id\":\"m1\","
        "\"namespace\":\"session-a\",\"source_type\":\"user_assertion\",\"source_authority\":1.0,"
        "\"relation_memory_ids\":[\"e1\"]}",
        response, sizeof(response)
    ) == MEMORIA_MOBILE_OK);
    assert(strstr(response, "\"memory_id\":\"e1\"") != NULL);

    assert(call_json(
        memoria_mobile_learn_turn_json, h,
        "{\"role\":\"user\",\"text\":\"voltage is 34v\",\"memory_id\":\"m2\","
        "\"namespace\":\"session-a\",\"source_type\":\"direct_observation\",\"source_authority\":1.0,"
        "\"relation_memory_ids\":[\"e2\"]}",
        response, sizeof(response)
    ) == MEMORIA_MOBILE_OK);
    assert(strstr(response, "\"memory_id\":\"e2\"") != NULL);

    /* Existing direct evidence must keep precedence even when relation anchors are supplied. */
    assert(call_json(
        memoria_mobile_resolve_context_json, h,
        "{\"query\":\"charger is voltage\",\"namespace\":\"session-a\",\"concept_namespace\":\"semantic\","
        "\"relation_source\":\"charger\",\"relation_target\":\"34v\"}",
        response, sizeof(response)
    ) == MEMORIA_MOBILE_OK);
    assert(strstr(response, "\"status\":\"HIT\"") != NULL);
    assert(strstr(response, "\"relation_inference_used\":true") == NULL);

    /* A lexical miss may use the already-persisted relation graph, but only with explicit anchors. */
    assert(call_json(
        memoria_mobile_resolve_context_json, h,
        "{\"query\":\"relationship check\",\"namespace\":\"session-a\",\"concept_namespace\":\"semantic\","
        "\"relation_source\":\"charger\",\"relation_target\":\"34v\"}",
        response, sizeof(response)
    ) == MEMORIA_MOBILE_OK);
    assert(strstr(response, "\"relation_inference_used\":true") != NULL);
    assert(strstr(response, "\"inference_hops\":2") != NULL);
    assert(strstr(response, "\"e1\"") != NULL);
    assert(strstr(response, "\"e2\"") != NULL);
    assert(strstr(response, "concept:voltage") != NULL);

    /* Namespace isolation remains fail-closed. */
    assert(call_json(
        memoria_mobile_resolve_context_json, h,
        "{\"query\":\"relationship check\",\"namespace\":\"other\",\"concept_namespace\":\"semantic\","
        "\"relation_source\":\"charger\",\"relation_target\":\"34v\"}",
        response, sizeof(response)
    ) == MEMORIA_MOBILE_UNRESOLVED);
    assert(strstr(response, "\"status\":\"UNRESOLVED\"") != NULL);

    /* Without explicit anchors, legacy resolver behavior is unchanged. */
    assert(call_json(
        memoria_mobile_resolve_context_json, h,
        "{\"query\":\"relationship check\",\"namespace\":\"session-a\",\"concept_namespace\":\"semantic\"}",
        response, sizeof(response)
    ) == MEMORIA_MOBILE_UNRESOLVED);
    assert(strstr(response, "\"status\":\"UNRESOLVED\"") != NULL);

    memoria_mobile_close(h);
    return 0;
}
