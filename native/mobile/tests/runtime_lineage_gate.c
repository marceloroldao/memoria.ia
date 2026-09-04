#include "memoria_mobile.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CHECK(expr) do { if (!(expr)) { fprintf(stderr,"CHECK failed: %s (%s:%d)\n",#expr,__FILE__,__LINE__); return 1; } } while (0)

static memoria_mobile_status learn(memoria_mobile_handle *h, const char *json, memoria_mobile_buffer *out) {
    memoria_mobile_buffer in = {(const uint8_t *)json, strlen(json)};
    return memoria_mobile_learn_turn_json(h, in, out);
}

static memoria_mobile_status resolve(memoria_mobile_handle *h, const char *json, memoria_mobile_buffer *out) {
    memoria_mobile_buffer in = {(const uint8_t *)json, strlen(json)};
    return memoria_mobile_resolve_context_json(h, in, out);
}

static int contains(memoria_mobile_buffer b, const char *needle) {
    return b.data && strstr((const char *)b.data, needle) != NULL;
}

int main(void) {
    memoria_mobile_handle *h = NULL;
    memoria_mobile_buffer out = {0};
    (void)system("rm -rf ./tmp-mobile-runtime-lineage-gate");

    CHECK(memoria_mobile_open("./tmp-mobile-runtime-lineage-gate", "org-runtime-lineage", &h) == MEMORIA_MOBILE_OK);

    CHECK(learn(h,
        "{\"role\":\"user\",\"text\":\"certificate is valid\",\"memory_id\":\"root-a\",\"namespace\":\"s\",\"order\":1,\"source_authority\":1.0,\"relation_memory_ids\":[\"root-a-rel\"]}",
        &out) == MEMORIA_MOBILE_OK);
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};

    CHECK(learn(h,
        "{\"role\":\"user\",\"text\":\"owner is alice\",\"memory_id\":\"root-b\",\"namespace\":\"s\",\"order\":2,\"source_authority\":1.0,\"relation_memory_ids\":[\"root-b-rel\"]}",
        &out) == MEMORIA_MOBILE_OK);
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};

    CHECK(learn(h,
        "{\"role\":\"assistant\",\"text\":\"zephyrax is quartzmarker\",\"memory_id\":\"derived\",\"namespace\":\"s\",\"order\":3,\"source_type\":\"derived_relation\",\"source_authority\":0.9,\"parent_memory_ids\":[\"root-a-rel\",\"root-b-rel\"],\"relation_memory_ids\":[\"derived-rel\"]}",
        &out) == MEMORIA_MOBILE_OK);
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};

    CHECK(resolve(h, "{\"query\":\"zephyrax quartzmarker\",\"namespace\":\"s\"}", &out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "zephyrax"));
    CHECK(contains(out, "quartzmarker"));
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};

    CHECK(learn(h,
        "{\"role\":\"user\",\"text\":\"owner is bob\",\"memory_id\":\"root-b-fix\",\"namespace\":\"s\",\"order\":4,\"source_authority\":1.0,\"corrects_memory_ids\":[\"root-b\"],\"relation_memory_ids\":[\"root-b-fix-rel\"]}",
        &out) == MEMORIA_MOBILE_OK);
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};

    CHECK(resolve(h, "{\"query\":\"zephyrax quartzmarker\",\"namespace\":\"s\"}", &out) == MEMORIA_MOBILE_UNRESOLVED);
    CHECK(contains(out, "UNRESOLVED"));
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};

    CHECK(memoria_mobile_flush(h) == MEMORIA_MOBILE_OK);
    memoria_mobile_close(h); h = NULL;

    CHECK(memoria_mobile_open("./tmp-mobile-runtime-lineage-gate", "org-runtime-lineage", &h) == MEMORIA_MOBILE_OK);
    CHECK(resolve(h, "{\"query\":\"zephyrax quartzmarker\",\"namespace\":\"s\"}", &out) == MEMORIA_MOBILE_UNRESOLVED);
    CHECK(contains(out, "UNRESOLVED"));
    memoria_mobile_free_buffer(out);

    memoria_mobile_close(h);
    (void)system("rm -rf ./tmp-mobile-runtime-lineage-gate");
    return 0;
}
