#include "memoria_mobile.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CHECK(expr) do { if (!(expr)) { fprintf(stderr,"CHECK failed: %s (%s:%d)\n",#expr,__FILE__,__LINE__); return 1; } } while (0)

static memoria_mobile_status call_learn(memoria_mobile_handle *h, const char *json, memoria_mobile_buffer *out) {
    memoria_mobile_buffer in = {(const uint8_t *)json, strlen(json)};
    return memoria_mobile_learn_turn_json(h, in, out);
}

static memoria_mobile_status call_episode(memoria_mobile_handle *h, const char *json, memoria_mobile_buffer *out) {
    memoria_mobile_buffer in = {(const uint8_t *)json, strlen(json)};
    return memoria_mobile_store_episode_json(h, in, out);
}

static memoria_mobile_status call_resolve(memoria_mobile_handle *h, const char *json, memoria_mobile_buffer *out) {
    memoria_mobile_buffer in = {(const uint8_t *)json, strlen(json)};
    return memoria_mobile_resolve_context_json(h, in, out);
}

static memoria_mobile_status call_export(memoria_mobile_handle *h, const char *json, memoria_mobile_buffer *out) {
    memoria_mobile_buffer in = {(const uint8_t *)json, strlen(json)};
    return memoria_mobile_export_snapshot_json(h, in, out);
}

static int contains(memoria_mobile_buffer b, const char *needle) {
    return b.data && strstr((const char *)b.data, needle) != NULL;
}

int main(void) {
    memoria_mobile_handle *h = NULL;
    memoria_mobile_buffer out = {0};
    (void)system("rm -rf ./tmp-mobile-diagnostic-export");

    CHECK(memoria_mobile_open("./tmp-mobile-diagnostic-export", "org-diagnostic", &h) == MEMORIA_MOBILE_OK);

    CHECK(call_learn(h,
        "{\"role\":\"user\",\"text\":\"sensor alpha mode is standby\",\"order\":1}", &out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "\"stored_memory_ids\":[\"mobile:1\"]"));
    memoria_mobile_free_buffer(out); out=(memoria_mobile_buffer){0};

    CHECK(call_episode(h,
        "{\"role\":\"user\",\"text\":\"revisão em português concluída\",\"timestamp\":\"2026-08-29T10:00:00-03:00\",\"event_type\":\"review\",\"topics_csv\":\"diagnostico,portugues\",\"order\":2}", &out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "\"episode_id\":\"episode:2\""));
    memoria_mobile_free_buffer(out); out=(memoria_mobile_buffer){0};

    CHECK(call_resolve(h, "{\"query\":\"sensor alpha mode\"}", &out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "\"memory_ids\":[\"mobile:1\"]"));
    memoria_mobile_free_buffer(out); out=(memoria_mobile_buffer){0};

    CHECK(call_export(h, "{\"turn_limit\":1,\"episode_limit\":1}", &out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "\"format\":\"memoria.mobile.diagnostic.v1\""));
    CHECK(contains(out, "\"organization_id\":\"org-diagnostic\""));
    CHECK(contains(out, "\"counts\":{\"turns\":1,\"episodes\":1}"));
    CHECK(contains(out, "\"memory_id\":\"mobile:1\""));
    CHECK(contains(out, "sensor alpha mode is standby"));
    CHECK(contains(out, "\"episode_id\":\"episode:2\""));
    CHECK(contains(out, "revisão em português concluída"));
    CHECK(contains(out, "\"next_offset\":null"));
    memoria_mobile_free_buffer(out); out=(memoria_mobile_buffer){0};

    /* Export is read-only: the next generated ID must be unaffected. */
    CHECK(call_learn(h,
        "{\"role\":\"user\",\"text\":\"sensor beta mode is active\",\"order\":3}", &out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "\"stored_memory_ids\":[\"mobile:3\"]"));
    memoria_mobile_free_buffer(out); out=(memoria_mobile_buffer){0};

    /* Pagination returns only the requested turn page. */
    CHECK(call_export(h, "{\"turn_offset\":0,\"turn_limit\":1,\"episode_limit\":1}", &out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "\"turn_page\":{\"offset\":0,\"limit\":1,\"returned\":1,\"next_offset\":1}"));
    CHECK(contains(out, "\"memory_id\":\"mobile:1\""));
    CHECK(!contains(out, "\"memory_id\":\"mobile:3\""));
    memoria_mobile_free_buffer(out); out=(memoria_mobile_buffer){0};

    CHECK(call_export(h, "{\"turn_offset\":1,\"turn_limit\":1,\"episode_limit\":1}", &out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "\"memory_id\":\"mobile:3\""));
    CHECK(!contains(out, "\"memory_id\":\"mobile:1\""));
    memoria_mobile_free_buffer(out); out=(memoria_mobile_buffer){0};

    CHECK(memoria_mobile_flush(h) == MEMORIA_MOBILE_OK);
    memoria_mobile_close(h); h = NULL;

    CHECK(memoria_mobile_open("./tmp-mobile-diagnostic-export", "org-diagnostic", &h) == MEMORIA_MOBILE_OK);
    CHECK(call_export(h, "{}", &out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "\"counts\":{\"turns\":2,\"episodes\":1}"));
    CHECK(contains(out, "\"memory_id\":\"mobile:1\""));
    CHECK(contains(out, "\"memory_id\":\"mobile:3\""));
    CHECK(contains(out, "\"episode_id\":\"episode:2\""));
    memoria_mobile_free_buffer(out); out=(memoria_mobile_buffer){0};

    CHECK(call_resolve(h, "{\"query\":\"sensor alpha mode\"}", &out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "\"memory_ids\":[\"mobile:1\"]"));
    memoria_mobile_free_buffer(out);

    memoria_mobile_close(h);
    (void)system("rm -rf ./tmp-mobile-diagnostic-export");
    return 0;
}
