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

static void learn(memoria_mobile_handle *h, const char *text, const char *memory_id, char *response, size_t response_cap) {
    char request[1024];
    snprintf(
        request,
        sizeof(request),
        "{\"role\":\"user\",\"text\":\"%s\",\"memory_id\":\"%s\","
        "\"namespace\":\"session-a\",\"source_type\":\"user_assertion\",\"source_authority\":1.0}",
        text,
        memory_id
    );
    assert(call_json(memoria_mobile_learn_turn_json, h, request, response, response_cap) == MEMORIA_MOBILE_OK);
}

static memoria_mobile_status resolve(memoria_mobile_handle *h, const char *query, int concepts, char *response, size_t response_cap) {
    char request[1024];
    snprintf(
        request,
        sizeof(request),
        concepts
            ? "{\"query\":\"%s\",\"namespace\":\"session-a\",\"concept_namespace\":\"semantic\"}"
            : "{\"query\":\"%s\",\"namespace\":\"session-a\"}",
        query
    );
    return call_json(memoria_mobile_resolve_context_json, h, request, response, response_cap);
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
        "\"fingerprint\":\"sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd\","
        "\"concept_count\":4,\"rows\":["
        "\"15:concept:voltage8:semantic7:voltage8:electric2:7:voltage3:ddp1:7:circuit\","
        "\"20:concept:bank-finance8:semantic19:finance institution7:finance2:19:finance institution4:bank2:4:loan6:credit\","
        "\"18:concept:bank-river8:semantic10:river edge9:geography2:10:river edge4:bank2:5:river5:water\","
        "\"21:concept:direct-target8:semantic16:canonical target10:precedence2:16:canonical target6:direct0:\"]}",
        response, sizeof(response)
    ) == MEMORIA_MOBILE_OK);
    assert(strstr(response, "\"status\":\"OK\"") != NULL);

    learn(h, "voltage", "m-voltage", response, sizeof(response));
    learn(h, "finance institution", "m-finance", response, sizeof(response));
    learn(h, "river edge", "m-river", response, sizeof(response));
    learn(h, "direct", "m-direct", response, sizeof(response));
    learn(h, "canonical target", "m-target", response, sizeof(response));

    /* Alias rewriting remains opt-in through a distinct concept namespace. */
    assert(resolve(h, "ddp", 0, response, sizeof(response)) == MEMORIA_MOBILE_UNRESOLVED);
    assert(strstr(response, "\"status\":\"UNRESOLVED\"") != NULL);
    assert(resolve(h, "ddp", 1, response, sizeof(response)) == MEMORIA_MOBILE_OK);
    assert(strstr(response, "\"status\":\"HIT\"") != NULL);
    assert(strstr(response, "voltage") != NULL);

    /* Original query always wins: never rewrite an already justified HIT. */
    assert(resolve(h, "direct", 1, response, sizeof(response)) == MEMORIA_MOBILE_OK);
    assert(strstr(response, "\"status\":\"HIT\"") != NULL);
    assert(strstr(response, "direct") != NULL);
    assert(strstr(response, "canonical target") == NULL);

    /* Polysemous alias without an explicit cue must not be guessed. */
    assert(resolve(h, "bank", 1, response, sizeof(response)) == MEMORIA_MOBILE_UNRESOLVED);
    assert(strstr(response, "\"status\":\"UNRESOLVED\"") != NULL);

    /* One explicit cue selects exactly one sense and retries its canonical query. */
    assert(resolve(h, "loan bank", 1, response, sizeof(response)) == MEMORIA_MOBILE_OK);
    assert(strstr(response, "finance institution") != NULL);
    assert(strstr(response, "river edge") == NULL);

    assert(resolve(h, "water bank", 1, response, sizeof(response)) == MEMORIA_MOBILE_OK);
    assert(strstr(response, "river edge") != NULL);
    assert(strstr(response, "finance institution") == NULL);

    /* Conflicting cues keep the alias ambiguous and therefore block retry. */
    assert(resolve(h, "loan water bank", 1, response, sizeof(response)) == MEMORIA_MOBILE_UNRESOLVED);
    assert(strstr(response, "\"status\":\"UNRESOLVED\"") != NULL);

    memoria_mobile_close(h);
    return 0;
}
