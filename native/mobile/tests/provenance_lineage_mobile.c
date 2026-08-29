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

static int assert_after_correction(memoria_mobile_handle *h) {
    memoria_mobile_buffer out = {0};
    memoria_mobile_buffer snapshot_req = {(const uint8_t *)"{}", 2};

    CHECK(resolve(h, "{\"query\":\"box code\",\"namespace\":\"s\"}", &out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "\"memory_ids\":[\"correction\"]"));
    CHECK(contains(out, "4729"));
    CHECK(!contains(out, "1111"));
    CHECK(contains(out, "\"ultimate_source_memory_id\":\"correction\""));
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};

    CHECK(memoria_mobile_export_snapshot_json(h, snapshot_req, &out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "\"memory_id\":\"root\""));
    CHECK(contains(out, "\"superseded_by\":\"correction\""));
    CHECK(contains(out, "\"created_time\":\"2026-08-29T12:00:00Z\""));
    CHECK(contains(out, "\"memory_id\":\"echo\""));
    CHECK(contains(out, "\"parent_memory_ids\":[\"root-rel\"]"));
    CHECK(contains(out, "\"ultimate_source_memory_id\":\"root\""));
    CHECK(contains(out, "\"memory_id\":\"correction\""));
    CHECK(contains(out, "\"parent_memory_ids\":[\"root\"]"));
    memoria_mobile_free_buffer(out);
    return 0;
}

int main(void) {
    memoria_mobile_handle *h = NULL;
    memoria_mobile_buffer out = {0};
    (void)system("rm -rf ./tmp-mobile-provenance-lineage");

    CHECK(memoria_mobile_open("./tmp-mobile-provenance-lineage", "org-lineage", &h) == MEMORIA_MOBILE_OK);

    CHECK(learn(h,
        "{\"role\":\"user\",\"text\":\"box code is 1111\",\"memory_id\":\"root\",\"namespace\":\"s\",\"order\":1,\"timestamp\":\"2026-08-29T12:00:00Z\",\"source_authority\":0.95,\"relation_memory_ids\":[\"root-rel\"]}",
        &out) == MEMORIA_MOBILE_OK);
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};

    /* Parent may reference a derived relation id; native lineage must trace relation -> turn -> root. */
    CHECK(learn(h,
        "{\"role\":\"assistant\",\"text\":\"box code is 1111\",\"memory_id\":\"echo\",\"namespace\":\"s\",\"order\":2,\"timestamp\":\"2026-08-29T12:01:00Z\",\"source_authority\":0.25,\"parent_memory_ids\":[\"root-rel\"],\"relation_memory_ids\":[\"echo-rel\"]}",
        &out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "\"parent_count\":1"));
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};

    CHECK(resolve(h, "{\"query\":\"box code\",\"namespace\":\"s\"}", &out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "\"memory_ids\":[\"root\"]"));
    CHECK(contains(out, "\"source_type\":\"user_assertion\""));
    CHECK(contains(out, "\"ultimate_source_memory_id\":\"root\""));
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};

    /* Parents cannot cross persistent namespaces. */
    CHECK(learn(h,
        "{\"role\":\"assistant\",\"text\":\"box code is 1111\",\"memory_id\":\"bad-cross\",\"namespace\":\"other\",\"parent_memory_ids\":[\"root\"]}",
        &out) == MEMORIA_MOBILE_INVALID_ARGUMENT);
    if (out.data) memoria_mobile_free_buffer(out);
    out = (memoria_mobile_buffer){0};

    CHECK(learn(h,
        "{\"role\":\"user\",\"text\":\"box code is 4729\",\"memory_id\":\"correction\",\"namespace\":\"s\",\"order\":3,\"timestamp\":\"2026-08-29T12:02:00Z\",\"source_authority\":1.0,\"corrects_memory_ids\":[\"root\"],\"relation_memory_ids\":[\"correction-rel\"]}",
        &out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "\"correction_applied\":true"));
    CHECK(contains(out, "\"parent_count\":1"));
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};

    /* The assistant echo's entire explicit lineage now terminates in a superseded root. */
    CHECK(assert_after_correction(h) == 0);
    CHECK(memoria_mobile_flush(h) == MEMORIA_MOBILE_OK);
    memoria_mobile_close(h); h = NULL;

    CHECK(memoria_mobile_open("./tmp-mobile-provenance-lineage", "org-lineage", &h) == MEMORIA_MOBILE_OK);
    CHECK(assert_after_correction(h) == 0);

    memoria_mobile_close(h);
    (void)system("rm -rf ./tmp-mobile-provenance-lineage");
    return 0;
}
