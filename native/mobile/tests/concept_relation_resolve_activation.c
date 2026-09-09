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

static void assert_inferred_hit(memoria_mobile_handle *h, const char *query, char *response, size_t cap) {
    char request[2048];
    snprintf(request, sizeof(request),
        "{\"query\":\"%s\",\"namespace\":\"session-a\",\"concept_namespace\":\"semantic\"}", query);
    assert(call_json(memoria_mobile_resolve_context_json, h, request, response, cap) == MEMORIA_MOBILE_OK);
    assert(strstr(response, "\"relation_inference_used\":true") != NULL);
    assert(strstr(response, "\"relation_anchors_inferred\":true") != NULL);
    assert(strstr(response, "\"inference_hops\":2") != NULL);
}

static void assert_neighborhood_hit(memoria_mobile_handle *h, const char *query, char *response, size_t cap) {
    char request[2048];
    snprintf(request, sizeof(request),
        "{\"query\":\"%s\",\"namespace\":\"session-a\",\"concept_namespace\":\"semantic\"}", query);
    assert(call_json(memoria_mobile_resolve_context_json, h, request, response, cap) == MEMORIA_MOBILE_OK);
    assert(strstr(response, "\"relation_neighborhood_used\":true") != NULL);
    assert(strstr(response, "\"neighborhood_hops\":1") != NULL);
    assert(strstr(response, "\"neighborhood_count\":1") != NULL);
    assert(strstr(response, "concept:voltage") != NULL);
    assert(strstr(response, "\"e1\"") != NULL);
}

static void assert_collection_hit(memoria_mobile_handle *h, const char *query, char *response, size_t cap) {
    char request[2048];
    snprintf(request, sizeof(request),
        "{\"query\":\"%s\",\"namespace\":\"session-a\",\"concept_namespace\":\"semantic\"}", query);
    assert(call_json(memoria_mobile_resolve_context_json, h, request, response, cap) == MEMORIA_MOBILE_OK);
    assert(strstr(response, "\"type_collection_used\":true") != NULL);
    assert(strstr(response, "\"collection_count\":2") != NULL);
    assert(strstr(response, "\"collection_type\":\"gato\"") != NULL);
    assert(strstr(response, "surface:alt") != NULL);
    assert(strstr(response, "surface:luna") != NULL);
    assert(strstr(response, "\"cat-e1\"") != NULL);
    assert(strstr(response, "\"cat-e2\"") != NULL);
    assert(strstr(response, "surface:animal") == NULL);
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

    assert(call_json(memoria_mobile_learn_turn_json, h,
        "{\"role\":\"user\",\"text\":\"charger is voltage\",\"memory_id\":\"m1\",\"namespace\":\"session-a\",\"source_type\":\"user_assertion\",\"source_authority\":1.0,\"relation_memory_ids\":[\"e1\"]}", response, sizeof(response)) == MEMORIA_MOBILE_OK);
    assert(call_json(memoria_mobile_learn_turn_json, h,
        "{\"role\":\"user\",\"text\":\"voltage is 34v\",\"memory_id\":\"m2\",\"namespace\":\"session-a\",\"source_type\":\"direct_observation\",\"source_authority\":1.0,\"relation_memory_ids\":[\"e2\"]}", response, sizeof(response)) == MEMORIA_MOBILE_OK);

    assert(call_json(memoria_mobile_learn_turn_json, h,
        "{\"role\":\"user\",\"text\":\"Alt é um gato\",\"memory_id\":\"cat-m1\",\"namespace\":\"session-a\",\"source_type\":\"user_assertion\",\"source_authority\":1.0,\"relation_memory_ids\":[\"cat-e1\"]}", response, sizeof(response)) == MEMORIA_MOBILE_OK);
    assert(call_json(memoria_mobile_learn_turn_json, h,
        "{\"role\":\"user\",\"text\":\"Luna é um gato\",\"memory_id\":\"cat-m2\",\"namespace\":\"session-a\",\"source_type\":\"direct_observation\",\"source_authority\":1.0,\"relation_memory_ids\":[\"cat-e2\"]}", response, sizeof(response)) == MEMORIA_MOBILE_OK);
    assert(call_json(memoria_mobile_learn_turn_json, h,
        "{\"role\":\"user\",\"text\":\"gato é um animal\",\"memory_id\":\"cat-m3\",\"namespace\":\"session-a\",\"source_type\":\"user_assertion\",\"source_authority\":1.0,\"relation_memory_ids\":[\"cat-e3\"]}", response, sizeof(response)) == MEMORIA_MOBILE_OK);

    assert(call_json(memoria_mobile_learn_turn_json, h,
        "{\"role\":\"user\",\"text\":\"internet is PPPoE\",\"memory_id\":\"net-m1\",\"namespace\":\"session-a\",\"source_type\":\"direct_observation\",\"source_authority\":1.0,\"relation_memory_ids\":[\"net-e1\"]}", response, sizeof(response)) == MEMORIA_MOBILE_OK);
    assert(call_json(memoria_mobile_learn_turn_json, h,
        "{\"role\":\"user\",\"text\":\"PPPoE is OLT\",\"memory_id\":\"net-m2\",\"namespace\":\"session-a\",\"source_type\":\"direct_observation\",\"source_authority\":1.0,\"relation_memory_ids\":[\"net-e2\"]}", response, sizeof(response)) == MEMORIA_MOBILE_OK);
    assert(call_json(memoria_mobile_learn_turn_json, h,
        "{\"role\":\"user\",\"text\":\"OLT is POP\",\"memory_id\":\"net-m3\",\"namespace\":\"session-a\",\"source_type\":\"direct_observation\",\"source_authority\":1.0,\"relation_memory_ids\":[\"net-e3\"]}", response, sizeof(response)) == MEMORIA_MOBILE_OK);
    assert(call_json(memoria_mobile_activate_relations_json, h,
        "{\"concept\":\"internet\",\"namespace\":\"session-a\",\"concept_namespace\":\"semantic\",\"depth\":2,\"budget\":1200,\"hop_decay\":0.72,\"min_confidence\":0.45}", response, sizeof(response)) == MEMORIA_MOBILE_OK);
    assert(strstr(response, "\"native_structural_activation\":true") != NULL);
    assert(strstr(response, "\"relation_count\":2") != NULL);

    assert(call_json(memoria_mobile_resolve_context_json, h,
        "{\"query\":\"charger is voltage\",\"namespace\":\"session-a\",\"concept_namespace\":\"semantic\",\"relation_source\":\"charger\",\"relation_target\":\"34v\"}", response, sizeof(response)) == MEMORIA_MOBILE_OK);
    assert(strstr(response, "\"relation_inference_used\":true") == NULL);

    assert(call_json(memoria_mobile_resolve_context_json, h,
        "{\"query\":\"relationship check\",\"namespace\":\"session-a\",\"concept_namespace\":\"semantic\",\"relation_source\":\"charger\",\"relation_target\":\"34v\"}", response, sizeof(response)) == MEMORIA_MOBILE_OK);
    assert(strstr(response, "\"relation_anchors_inferred\":false") != NULL);

    assert_inferred_hit(h, "What is the relation between charger and 34v?", response, sizeof(response));
    assert_inferred_hit(h, "Qual a relação entre charger e 34v?", response, sizeof(response));
    assert_inferred_hit(h, "How is charger related to 34v?", response, sizeof(response));
    assert_inferred_hit(h, "Is charger related to 34v?", response, sizeof(response));
    assert_inferred_hit(h, "What connects charger to 34v?", response, sizeof(response));
    assert_inferred_hit(h, "Como charger se relaciona com 34v?", response, sizeof(response));
    assert_inferred_hit(h, "O que conecta charger a 34v?", response, sizeof(response));
    assert_inferred_hit(h, "O que liga charger a 34v?", response, sizeof(response));

    assert_collection_hit(h, "Quais gatos você conhece?", response, sizeof(response));
    assert_collection_hit(h, "Quais gatos voce conhece?", response, sizeof(response));
    assert_collection_hit(h, "qual nome dos meus gatos?", response, sizeof(response));
    assert_collection_hit(h, "qual o nome dos meus gatos?", response, sizeof(response));
    assert_collection_hit(h, "quais são os meus gatos?", response, sizeof(response));

    assert_neighborhood_hit(h, "What is related to charger?", response, sizeof(response));
    assert_neighborhood_hit(h, "O que está relacionado a charger?", response, sizeof(response));
    assert_neighborhood_hit(h, "O que esta ligado a charger?", response, sizeof(response));

    assert(call_json(memoria_mobile_resolve_context_json, h,
        "{\"query\":\"relation between charger and 34v\",\"namespace\":\"other\",\"concept_namespace\":\"semantic\"}", response, sizeof(response)) == MEMORIA_MOBILE_UNRESOLVED);
    assert(call_json(memoria_mobile_resolve_context_json, h,
        "{\"query\":\"what is related to charger?\",\"namespace\":\"other\",\"concept_namespace\":\"semantic\"}", response, sizeof(response)) == MEMORIA_MOBILE_UNRESOLVED);
    assert(call_json(memoria_mobile_resolve_context_json, h,
        "{\"query\":\"Quais gatos você conhece?\",\"namespace\":\"other\",\"concept_namespace\":\"semantic\"}", response, sizeof(response)) == MEMORIA_MOBILE_UNRESOLVED);

    assert(call_json(memoria_mobile_resolve_context_json, h,
        "{\"query\":\"charger and 34v maybe similar\",\"namespace\":\"session-a\",\"concept_namespace\":\"semantic\"}", response, sizeof(response)) == MEMORIA_MOBILE_UNRESOLVED);
    assert(call_json(memoria_mobile_resolve_context_json, h,
        "{\"query\":\"charger relations\",\"namespace\":\"session-a\",\"concept_namespace\":\"semantic\"}", response, sizeof(response)) == MEMORIA_MOBILE_UNRESOLVED);
    assert(call_json(memoria_mobile_resolve_context_json, h,
        "{\"query\":\"gatos conhecidos talvez\",\"namespace\":\"session-a\",\"concept_namespace\":\"semantic\"}", response, sizeof(response)) == MEMORIA_MOBILE_UNRESOLVED);

    memoria_mobile_close(h);
    return 0;
}
