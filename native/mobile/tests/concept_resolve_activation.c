#include "memoria_mobile.h"

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
