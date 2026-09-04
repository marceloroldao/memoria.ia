#include "memoria_mobile.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CHECK(expr) do { if (!(expr)) { fprintf(stderr,"CHECK failed: %s (%s:%d)\n",#expr,__FILE__,__LINE__); return 1; } } while (0)

static memoria_mobile_status learn(memoria_mobile_handle *h, const char *json, memoria_mobile_buffer *out) {
    memoria_mobile_buffer in = {(const uint8_t *)json, strlen(json)};
    return memoria_mobile_learn_turn_json(h, in, out);
}

static memoria_mobile_status resolve(memoria_mobile_handle *h, const char *query, memoria_mobile_buffer *out) {
    char json[512];
    memoria_mobile_buffer in;
    snprintf(json, sizeof(json), "{\"query\":\"%s\",\"namespace\":\"s\"}", query);
    in.data = (const uint8_t *)json;
    in.size = strlen(json);
    return memoria_mobile_resolve_context_json(h, in, out);
}

static int contains(memoria_mobile_buffer b, const char *needle) {
    return b.data && strstr((const char *)b.data, needle) != NULL;
}

int main(void) {
    memoria_mobile_handle *h = NULL;
    memoria_mobile_buffer out = {0};
    (void)system("rm -rf ./tmp-mobile-auto-semantic-consolidation");

    CHECK(memoria_mobile_open("./tmp-mobile-auto-semantic-consolidation", "org-auto-semantic", &h) == MEMORIA_MOBILE_OK);

    CHECK(learn(h,
        "{\"role\":\"user\",\"text\":\"sensor is active\",\"memory_id\":\"root-a\",\"namespace\":\"s\",\"order\":1,\"source_authority\":1.0,\"relation_memory_ids\":[\"root-a-rel\"]}",
        &out) == MEMORIA_MOBILE_OK);
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};

    CHECK(learn(h,
        "{\"role\":\"user\",\"text\":\"sensor is active\",\"memory_id\":\"root-b\",\"namespace\":\"s\",\"order\":2,\"source_authority\":1.0,\"relation_memory_ids\":[\"root-b-rel\"]}",
        &out) == MEMORIA_MOBILE_OK);
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};

    /* Two independent factual roots must create a persisted derived relation. */
    CHECK(resolve(h, "sensor active", &out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "\"source_type\":\"derived_relation\""));
    CHECK(contains(out, "sensor is active"));
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};

    CHECK(memoria_mobile_flush(h) == MEMORIA_MOBILE_OK);
    memoria_mobile_close(h); h = NULL;
    CHECK(memoria_mobile_open("./tmp-mobile-auto-semantic-consolidation", "org-auto-semantic", &h) == MEMORIA_MOBILE_OK);
    CHECK(resolve(h, "sensor active", &out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "\"source_type\":\"derived_relation\""));
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};

    /* Correcting one support invalidates the old conjunction. */
    CHECK(learn(h,
        "{\"role\":\"user\",\"text\":\"sensor is inactive\",\"memory_id\":\"root-b-fix\",\"namespace\":\"s\",\"order\":4,\"source_authority\":1.0,\"corrects_memory_ids\":[\"root-b\"],\"relation_memory_ids\":[\"root-b-fix-rel\"]}",
        &out) == MEMORIA_MOBILE_OK);
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};

    CHECK(resolve(h, "sensor active", &out) == MEMORIA_MOBILE_OK);
    CHECK(!contains(out, "\"source_type\":\"derived_relation\""));
    CHECK(contains(out, "root-a"));
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};

    /* A new independent root may reconsolidate the still-supported claim. */
    CHECK(learn(h,
        "{\"role\":\"user\",\"text\":\"sensor is active\",\"memory_id\":\"root-c\",\"namespace\":\"s\",\"order\":5,\"source_authority\":1.0,\"relation_memory_ids\":[\"root-c-rel\"]}",
        &out) == MEMORIA_MOBILE_OK);
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};

    CHECK(resolve(h, "sensor active", &out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "\"source_type\":\"derived_relation\""));
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};

    CHECK(memoria_mobile_flush(h) == MEMORIA_MOBILE_OK);
    memoria_mobile_close(h); h = NULL;
    CHECK(memoria_mobile_open("./tmp-mobile-auto-semantic-consolidation", "org-auto-semantic", &h) == MEMORIA_MOBILE_OK);
    CHECK(resolve(h, "sensor active", &out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "\"source_type\":\"derived_relation\""));
    memoria_mobile_free_buffer(out);

    memoria_mobile_close(h);
    (void)system("rm -rf ./tmp-mobile-auto-semantic-consolidation");
    return 0;
}
