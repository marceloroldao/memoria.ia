#include "memoria_mobile.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CHECK(x) do { if (!(x)) { fprintf(stderr, "CHECK failed: %s:%d: %s\n", __FILE__, __LINE__, #x); return 1; } } while (0)

static memoria_mobile_status store(memoria_mobile_handle *h, const char *json, memoria_mobile_buffer *out) {
    memoria_mobile_buffer in = {(const uint8_t *)json, strlen(json)};
    return memoria_mobile_store_episode_json(h, in, out);
}

static memoria_mobile_status recall(memoria_mobile_handle *h, const char *json, memoria_mobile_buffer *out) {
    memoria_mobile_buffer in = {(const uint8_t *)json, strlen(json)};
    return memoria_mobile_recall_episode_json(h, in, out);
}

static int contains(memoria_mobile_buffer out, const char *needle) {
    return out.data && strstr((const char *)out.data, needle) != NULL;
}

int main(void) {
    const char *dir = "./tmp-mobile-dynamic-episodes";
    memoria_mobile_handle *h = NULL;
    memoria_mobile_buffer out = {0};
    char json[768];
    int i;

    (void)system("rm -rf ./tmp-mobile-dynamic-episodes");
    CHECK(memoria_mobile_open(dir, "dynamic-episodes", &h) == MEMORIA_MOBILE_OK);

    for (i = 1; i <= 1000; ++i) {
        snprintf(json, sizeof(json),
                 "{\"episode_id\":\"ep-%d\",\"session_id\":\"capacity\",\"role\":\"user\","
                 "\"text\":\"episode number %d\",\"event_type\":\"capacity-test\",\"topics_csv\":\"capacity\","
                 "\"order\":%d}", i, i, i);
        CHECK(store(h, json, &out) == MEMORIA_MOBILE_OK);
        CHECK(contains(out, "\"durable\":true"));
        memoria_mobile_free_buffer(out);
        out.data = NULL; out.size = 0;
    }

    CHECK(memoria_mobile_flush(h) == MEMORIA_MOBILE_OK);
    memoria_mobile_close(h);
    h = NULL;

    CHECK(memoria_mobile_open(dir, "dynamic-episodes", &h) == MEMORIA_MOBILE_OK);
    CHECK(recall(h,
        "{\"query\":\"episode number 1000\",\"session_id\":\"capacity\",\"event_type\":\"capacity-test\",\"topics_csv\":\"capacity\"}",
        &out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "ep-1000"));
    CHECK(contains(out, "episode number 1000"));
    memoria_mobile_free_buffer(out);

    memoria_mobile_close(h);
    (void)system("rm -rf ./tmp-mobile-dynamic-episodes");
    return 0;
}
