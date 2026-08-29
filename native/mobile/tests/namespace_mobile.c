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

static int assert_scopes(memoria_mobile_handle *h) {
    memoria_mobile_buffer out = {0};

    /* Semantic isolation uses one authoritative fact per namespace. */
    CHECK(resolve(h, "{\"query\":\"workspace\",\"namespace\":\"s1\"}", &out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "\"memory_ids\":[\"s1-workspace\"]"));
    CHECK(contains(out, "workspace is alpha"));
    CHECK(!contains(out, "beta"));
    CHECK(!contains(out, "global"));
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};

    CHECK(resolve(h, "{\"query\":\"workspace\",\"namespace\":\"s2\"}", &out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "\"memory_ids\":[\"s2-workspace\"]"));
    CHECK(contains(out, "workspace is beta"));
    CHECK(!contains(out, "alpha"));
    CHECK(!contains(out, "global"));
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};

    CHECK(resolve(h, "{\"query\":\"workspace\"}", &out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "\"memory_ids\":[\"default-workspace\"]"));
    CHECK(contains(out, "workspace is global"));
    CHECK(!contains(out, "alpha"));
    CHECK(!contains(out, "beta"));
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};

    /* Historical state remains independently scoped. */
    CHECK(resolve(h, "{\"query\":\"what was device mode before and what is current now?\",\"namespace\":\"s1\"}", &out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "\"temporal_state_used\":true"));
    CHECK(contains(out, "\"previous_memory_id\":\"s1-old\""));
    CHECK(contains(out, "\"current_memory_id\":\"s1-new\""));
    CHECK(contains(out, "\"previous_value\":\"standby\""));
    CHECK(contains(out, "\"current_value\":\"active\""));
    CHECK(!contains(out, "broken"));
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};

    CHECK(resolve(h, "{\"query\":\"what is current device mode now?\",\"namespace\":\"s2\"}", &out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "\"temporal_state_used\":true"));
    CHECK(contains(out, "\"current_memory_id\":\"s2-device\""));
    CHECK(contains(out, "\"current_value\":\"broken\""));
    CHECK(!contains(out, "active"));
    memoria_mobile_free_buffer(out);
    return 0;
}

int main(void) {
    memoria_mobile_handle *h = NULL;
    memoria_mobile_buffer out = {0};
    memoria_mobile_buffer snapshot_req = {(const uint8_t *)"{}", 2};
    (void)system("rm -rf ./tmp-mobile-namespace");

    CHECK(memoria_mobile_open("./tmp-mobile-namespace", "org-namespace", &h) == MEMORIA_MOBILE_OK);

    CHECK(learn(h, "{\"role\":\"user\",\"text\":\"workspace is alpha\",\"memory_id\":\"s1-workspace\",\"namespace\":\"s1\",\"order\":1}", &out) == MEMORIA_MOBILE_OK);
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};
    CHECK(learn(h, "{\"role\":\"user\",\"text\":\"workspace is beta\",\"memory_id\":\"s2-workspace\",\"namespace\":\"s2\",\"order\":2}", &out) == MEMORIA_MOBILE_OK);
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};
    CHECK(learn(h, "{\"role\":\"user\",\"text\":\"workspace is global\",\"memory_id\":\"default-workspace\",\"order\":3}", &out) == MEMORIA_MOBILE_OK);
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};

    CHECK(learn(h, "{\"role\":\"user\",\"text\":\"device mode is standby\",\"memory_id\":\"s1-old\",\"namespace\":\"s1\",\"order\":4}", &out) == MEMORIA_MOBILE_OK);
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};
    CHECK(learn(h, "{\"role\":\"user\",\"text\":\"device mode is broken\",\"memory_id\":\"s2-device\",\"namespace\":\"s2\",\"order\":5}", &out) == MEMORIA_MOBILE_OK);
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};
    CHECK(learn(h, "{\"role\":\"user\",\"text\":\"device mode is active\",\"memory_id\":\"s1-new\",\"namespace\":\"s1\",\"order\":6}", &out) == MEMORIA_MOBILE_OK);
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};

    /* A named namespace cannot supersede memory from another namespace. */
    CHECK(learn(h, "{\"role\":\"user\",\"text\":\"workspace is fixed\",\"memory_id\":\"cross\",\"namespace\":\"s1\",\"corrects_memory_ids\":[\"s2-workspace\"]}", &out) == MEMORIA_MOBILE_INVALID_ARGUMENT);
    if (out.data) memoria_mobile_free_buffer(out);
    out = (memoria_mobile_buffer){0};

    CHECK(assert_scopes(h) == 0);

    CHECK(memoria_mobile_export_snapshot_json(h, snapshot_req, &out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "\"namespace\":\"s1\""));
    CHECK(contains(out, "\"namespace\":\"s2\""));
    CHECK(contains(out, "\"namespace\":\"\""));
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};

    CHECK(memoria_mobile_flush(h) == MEMORIA_MOBILE_OK);
    memoria_mobile_close(h); h = NULL;

    CHECK(memoria_mobile_open("./tmp-mobile-namespace", "org-namespace", &h) == MEMORIA_MOBILE_OK);
    CHECK(assert_scopes(h) == 0);
    CHECK(memoria_mobile_export_snapshot_json(h, snapshot_req, &out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "\"namespace\":\"s1\""));
    CHECK(contains(out, "\"namespace\":\"s2\""));
    memoria_mobile_free_buffer(out);

    memoria_mobile_close(h);
    (void)system("rm -rf ./tmp-mobile-namespace");
    return 0;
}
