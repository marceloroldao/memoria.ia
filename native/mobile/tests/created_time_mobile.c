#include "memoria_mobile.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CHECK(expr) do { if (!(expr)) { fprintf(stderr,"CHECK failed: %s (%s:%d)\n",#expr,__FILE__,__LINE__); return 1; } } while (0)

static int contains(memoria_mobile_buffer b, const char *needle) {
    return b.data && strstr((const char *)b.data, needle) != NULL;
}

static memoria_mobile_status learn(memoria_mobile_handle *h, const char *json, memoria_mobile_buffer *out) {
    memoria_mobile_buffer in = {(const uint8_t *)json, strlen(json)};
    return memoria_mobile_learn_turn_json(h, in, out);
}

static memoria_mobile_status episode(memoria_mobile_handle *h, const char *json, memoria_mobile_buffer *out) {
    memoria_mobile_buffer in = {(const uint8_t *)json, strlen(json)};
    return memoria_mobile_store_episode_json(h, in, out);
}

static int snapshot_contract(memoria_mobile_handle *h, char generated[32]) {
    memoria_mobile_buffer req = {(const uint8_t *)"{}", 2};
    memoria_mobile_buffer out = {0};
    const char *p;
    CHECK(memoria_mobile_export_snapshot_json(h, req, &out) == MEMORIA_MOBILE_OK);
    p = strstr((const char *)out.data, "\"memory_id\":\"auto-time\"");
    CHECK(p != NULL);
    p = strstr(p, "\"created_time\":\"");
    CHECK(p != NULL);
    p += strlen("\"created_time\":\"");
    CHECK(strlen(p) >= 20);
    CHECK(p[4] == '-' && p[7] == '-' && p[10] == 'T' && p[13] == ':' && p[16] == ':' && p[19] == 'Z');
    memcpy(generated, p, 20);
    generated[20] = 0;
    CHECK(contains(out, "\"timestamp\":\"2026-01-02T03:04:05Z\""));
    memoria_mobile_free_buffer(out);
    return 0;
}

int main(void) {
    memoria_mobile_handle *h = NULL;
    memoria_mobile_buffer out = {0};
    char before[32] = {0};
    char after[32] = {0};
    (void)system("rm -rf ./tmp-mobile-created-time");

    CHECK(memoria_mobile_open("./tmp-mobile-created-time", "org-created-time", &h) == MEMORIA_MOBILE_OK);
    CHECK(learn(h, "{\"role\":\"user\",\"text\":\"clock is ready\",\"memory_id\":\"auto-time\",\"namespace\":\"s\"}", &out) == MEMORIA_MOBILE_OK);
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};

    CHECK(episode(h, "{\"role\":\"user\",\"text\":\"explicit episode\",\"episode_id\":\"explicit-episode\",\"session_id\":\"s\",\"timestamp\":\"2026-01-02T03:04:05Z\"}", &out) == MEMORIA_MOBILE_OK);
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};

    CHECK(snapshot_contract(h, before) == 0);
    CHECK(memoria_mobile_flush(h) == MEMORIA_MOBILE_OK);
    memoria_mobile_close(h); h = NULL;

    CHECK(memoria_mobile_open("./tmp-mobile-created-time", "org-created-time", &h) == MEMORIA_MOBILE_OK);
    CHECK(snapshot_contract(h, after) == 0);
    CHECK(strcmp(before, after) == 0);
    memoria_mobile_close(h);
    (void)system("rm -rf ./tmp-mobile-created-time");
    return 0;
}
