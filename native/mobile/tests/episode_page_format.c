#include "memoria_mobile.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CHECK(x) do { if (!(x)) { fprintf(stderr, "CHECK failed: %s:%d: %s\n", __FILE__, __LINE__, #x); return 1; } } while (0)

static memoria_mobile_status call_json(
    memoria_mobile_status (*fn)(memoria_mobile_handle *, memoria_mobile_buffer, memoria_mobile_buffer *),
    memoria_mobile_handle *h, const char *json, memoria_mobile_buffer *out
) {
    memoria_mobile_buffer in = {(const uint8_t *)json, strlen(json)};
    return fn(h, in, out);
}

static int contains(memoria_mobile_buffer out, const char *needle) {
    return out.data && strstr((const char *)out.data, needle) != NULL;
}

int main(void) {
    const char *dir = "./tmp-mobile-page-format";
    memoria_mobile_handle *h = NULL;
    memoria_mobile_buffer out = {0};
    char json[768];
    int i;

    (void)system("rm -rf ./tmp-mobile-page-format");
    CHECK(memoria_mobile_open(dir, "page-format", &h) == MEMORIA_MOBILE_OK);

    for (i = 1; i <= 300; ++i) {
        snprintf(json, sizeof(json),
                 "{\"episode_id\":\"ep-%d\",\"session_id\":\"temporal\",\"role\":\"user\","
                 "\"text\":\"raw episode %d\",\"event_type\":\"raw\",\"topics_csv\":\"raw\",\"order\":%d}",
                 i, i, i);
        CHECK(call_json(memoria_mobile_store_episode_json, h, json, &out) == MEMORIA_MOBILE_OK);
        memoria_mobile_free_buffer(out); out.data = NULL; out.size = 0;
    }

    CHECK(call_json(memoria_mobile_export_snapshot_json, h,
        "{\"turn_offset\":0,\"turn_limit\":1,\"episode_offset\":250,\"episode_limit\":64}", &out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "\"episodes\":300"));
    CHECK(contains(out, "\"offset\":250"));
    CHECK(contains(out, "\"returned\":50"));
    CHECK(contains(out, "\"episode_id\":\"ep-251\""));
    CHECK(contains(out, "\"episode_id\":\"ep-300\""));
    memoria_mobile_free_buffer(out); out.data = NULL; out.size = 0;

    CHECK(call_json(memoria_mobile_format_store_json, h, "{\"confirm\":\"NO\"}", &out) == MEMORIA_MOBILE_INVALID_ARGUMENT);
    memoria_mobile_free_buffer(out); out.data = NULL; out.size = 0;

    CHECK(call_json(memoria_mobile_format_store_json, h, "{\"confirm\":\"FORMATAR\"}", &out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "\"removed_episodes\":300"));
    memoria_mobile_free_buffer(out); out.data = NULL; out.size = 0;

    CHECK(call_json(memoria_mobile_export_snapshot_json, h,
        "{\"turn_offset\":0,\"turn_limit\":1,\"episode_offset\":0,\"episode_limit\":64}", &out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "\"episodes\":0"));
    memoria_mobile_free_buffer(out); out.data = NULL; out.size = 0;

    CHECK(memoria_mobile_flush(h) == MEMORIA_MOBILE_OK);
    memoria_mobile_close(h); h = NULL;
    CHECK(memoria_mobile_open(dir, "page-format", &h) == MEMORIA_MOBILE_OK);
    CHECK(call_json(memoria_mobile_export_snapshot_json, h,
        "{\"turn_offset\":0,\"turn_limit\":1,\"episode_offset\":0,\"episode_limit\":64}", &out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "\"episodes\":0"));
    memoria_mobile_free_buffer(out); out.data = NULL; out.size = 0;

    snprintf(json, sizeof(json),
             "{\"episode_id\":\"after-format\",\"session_id\":\"temporal\",\"role\":\"user\","
             "\"text\":\"fresh raw input\",\"event_type\":\"raw\",\"topics_csv\":\"raw\",\"order\":1}");
    CHECK(call_json(memoria_mobile_store_episode_json, h, json, &out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "\"durable\":true"));
    memoria_mobile_free_buffer(out);

    memoria_mobile_close(h);
    (void)system("rm -rf ./tmp-mobile-page-format");
    return 0;
}
