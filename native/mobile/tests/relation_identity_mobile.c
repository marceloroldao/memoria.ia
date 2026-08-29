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

static int assert_identity(memoria_mobile_handle *h, const char *query, const char *relation_id) {
    char request[256];
    memoria_mobile_buffer out = {0};
    snprintf(request, sizeof(request), "{\"query\":\"%s\"}", query);
    CHECK(resolve(h, request, &out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, relation_id));
    CHECK(contains(out, "\"source_memory_id\":"));
    memoria_mobile_free_buffer(out);
    return 0;
}

int main(void) {
    memoria_mobile_handle *h = NULL;
    memoria_mobile_buffer out = {0};
    memoria_mobile_buffer snapshot_req = {(const uint8_t *)"{}", 2};
    (void)system("rm -rf ./tmp-mobile-relation-identity");

    CHECK(memoria_mobile_open("./tmp-mobile-relation-identity", "org-rel-id", &h) == MEMORIA_MOBILE_OK);

    CHECK(learn(h,
        "{\"role\":\"user\",\"text\":\"sensor = active\",\"memory_id\":\"turn1\",\"order\":1,\"relation_memory_ids\":[\"rel1\"]}",
        &out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "\"stored_memory_ids\":[\"turn1\"]"));
    CHECK(contains(out, "\"memory_id\":\"rel1\""));
    CHECK(contains(out, "\"source_memory_id\":\"turn1\""));
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};

    CHECK(learn(h,
        "{\"role\":\"user\",\"text\":\"device = ready\",\"memory_id\":\"turn2\",\"order\":2}",
        &out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "\"memory_id\":\"turn2#relation:0\""));
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};

    CHECK(learn(h,
        "{\"role\":\"user\",\"text\":\"invalid = relation\",\"memory_id\":\"bad\",\"relation_memory_ids\":[]}",
        &out) == MEMORIA_MOBILE_INVALID_ARGUMENT);
    if (out.data) memoria_mobile_free_buffer(out);
    out = (memoria_mobile_buffer){0};

    CHECK(assert_identity(h, "sensor active", "\"memory_id\":\"rel1\"") == 0);
    CHECK(assert_identity(h, "device ready", "\"memory_id\":\"turn2#relation:0\"") == 0);

    CHECK(memoria_mobile_export_snapshot_json(h, snapshot_req, &out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "\"memory_id\":\"rel1\""));
    CHECK(contains(out, "\"memory_id\":\"turn2#relation:0\""));
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};

    CHECK(memoria_mobile_flush(h) == MEMORIA_MOBILE_OK);
    memoria_mobile_close(h); h = NULL;

    CHECK(memoria_mobile_open("./tmp-mobile-relation-identity", "org-rel-id", &h) == MEMORIA_MOBILE_OK);
    CHECK(assert_identity(h, "sensor active", "\"memory_id\":\"rel1\"") == 0);
    CHECK(assert_identity(h, "device ready", "\"memory_id\":\"turn2#relation:0\"") == 0);

    CHECK(memoria_mobile_export_snapshot_json(h, snapshot_req, &out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "\"memory_id\":\"rel1\""));
    CHECK(contains(out, "\"memory_id\":\"turn2#relation:0\""));
    memoria_mobile_free_buffer(out);

    memoria_mobile_close(h);
    (void)system("rm -rf ./tmp-mobile-relation-identity");
    return 0;
}
