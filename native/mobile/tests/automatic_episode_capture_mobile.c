#include "memoria_mobile.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CHECK(expr) do { if (!(expr)) { fprintf(stderr,"CHECK failed: %s (%s:%d)\n",#expr,__FILE__,__LINE__); return 1; } } while (0)

static memoria_mobile_buffer buf(const char *s) {
    memoria_mobile_buffer b = {(const uint8_t *)s, strlen(s)};
    return b;
}

static int contains(memoria_mobile_buffer b, const char *needle) {
    return b.data && strstr((const char *)b.data, needle) != NULL;
}

static memoria_mobile_status learn(memoria_mobile_handle *h, const char *json, memoria_mobile_buffer *out) {
    return memoria_mobile_learn_turn_json(h, buf(json), out);
}

static memoria_mobile_status recall(memoria_mobile_handle *h, const char *json, memoria_mobile_buffer *out) {
    return memoria_mobile_recall_episode_json(h, buf(json), out);
}

static int assert_latest_session_episode(memoria_mobile_handle *h) {
    memoria_mobile_buffer out = {0};
    CHECK(recall(h,
        "{\"query\":\"atlas battery stable\",\"session_id\":\"session-alpha\","
        "\"event_type\":\"conversation_turn\"}", &out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "\"episode_ids\":[\"turn:a2\"]"));
    CHECK(contains(out, "atlas battery remains stable"));
    CHECK(contains(out, "\"source_type\":\"assistant_generated\""));
    CHECK(contains(out, "\"source_authority\":0.350000"));
    CHECK(contains(out, "\"ultimate_source_memory_id\":\"a2\""));
    memoria_mobile_free_buffer(out);
    return 0;
}

int main(void) {
    const char *dir = "./tmp-mobile-auto-episode";
    memoria_mobile_handle *h = NULL;
    memoria_mobile_buffer out = {0};
    memoria_mobile_buffer snap = {0};

    (void)system("rm -rf ./tmp-mobile-auto-episode");
    CHECK(memoria_mobile_open(dir, "org-auto-episode", &h) == MEMORIA_MOBILE_OK);

    CHECK(learn(h,
        "{\"role\":\"user\",\"text\":\"atlas battery is stable\","
        "\"memory_id\":\"u1\",\"namespace\":\"session-alpha\","
        "\"timestamp\":\"2026-09-01T04:50:00Z\",\"order\":1}", &out) == MEMORIA_MOBILE_OK);
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};

    CHECK(learn(h,
        "{\"role\":\"assistant\",\"text\":\"atlas battery remains stable\","
        "\"memory_id\":\"a2\",\"namespace\":\"session-alpha\","
        "\"timestamp\":\"2026-09-01T04:51:00Z\",\"order\":2}", &out) == MEMORIA_MOBILE_OK);
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};

    /* Sessionless turns remain ordinary memory and are not auto-promoted to episodes. */
    CHECK(learn(h,
        "{\"role\":\"user\",\"text\":\"unscoped scratch note\","
        "\"memory_id\":\"loose\",\"order\":3}", &out) == MEMORIA_MOBILE_OK);
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};

    CHECK(assert_latest_session_episode(h) == 0);

    CHECK(memoria_mobile_export_snapshot_json(h, buf("{}"), &snap) == MEMORIA_MOBILE_OK);
    CHECK(contains(snap, "\"episode_id\":\"turn:u1\",\"session_id\":\"session-alpha\""));
    CHECK(contains(snap, "\"episode_id\":\"turn:a2\",\"session_id\":\"session-alpha\""));
    CHECK(!contains(snap, "\"episode_id\":\"turn:loose\""));
    memoria_mobile_free_buffer(snap); snap = (memoria_mobile_buffer){0};

    CHECK(memoria_mobile_flush(h) == MEMORIA_MOBILE_OK);
    memoria_mobile_close(h); h = NULL;

    CHECK(memoria_mobile_open(dir, "org-auto-episode", &h) == MEMORIA_MOBILE_OK);
    CHECK(assert_latest_session_episode(h) == 0);
    CHECK(memoria_mobile_export_snapshot_json(h, buf("{}"), &snap) == MEMORIA_MOBILE_OK);
    CHECK(contains(snap, "\"episode_id\":\"turn:u1\""));
    CHECK(contains(snap, "\"episode_id\":\"turn:a2\""));
    CHECK(!contains(snap, "\"episode_id\":\"turn:loose\""));
    memoria_mobile_free_buffer(snap);

    memoria_mobile_close(h);
    (void)system("rm -rf ./tmp-mobile-auto-episode");
    return 0;
}
