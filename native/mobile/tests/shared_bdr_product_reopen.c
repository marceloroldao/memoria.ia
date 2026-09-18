#include "memoria_mobile.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CHECK(x) do { if (!(x)) { fprintf(stderr, "CHECK failed: %s:%d: %s\n", __FILE__, __LINE__, #x); return 1; } } while (0)

static memoria_mobile_status call_json(
    memoria_mobile_status (*fn)(memoria_mobile_handle *, memoria_mobile_buffer, memoria_mobile_buffer *),
    memoria_mobile_handle *h,
    const char *json,
    memoria_mobile_buffer *out
) {
    memoria_mobile_buffer in = {(const uint8_t *)json, strlen(json)};
    return fn(h, in, out);
}

static int contains(memoria_mobile_buffer out, const char *needle) {
    return out.data && strstr((const char *)out.data, needle) != NULL;
}

int main(void) {
    const char *dir = "./tmp-mobile-shared-bdr-reopen";
    const char *org = "shared-bdr-reopen";
    const char *catalog =
        "{\"schema\":1,\"concept_count\":0,"
        "\"fingerprint\":\"sha256:0000000000000000000000000000000000000000000000000000000000000000\","
        "\"rows\":[]}";
    memoria_mobile_handle *h = NULL;
    memoria_mobile_buffer out = {0};
    char json[768];
    int i;

    (void)system("rm -rf ./tmp-mobile-shared-bdr-reopen");
    CHECK(memoria_mobile_open(dir, org, &h) == MEMORIA_MOBILE_OK);

    /* Product startup materializes the concept catalog after the canonical
       persistence handle is already open. This must use the same AtomicDatabase
       handle; a second writer can create an invalid/non-monotonic BDW4 stream. */
    CHECK(call_json(memoria_mobile_apply_concept_catalog_json, h, catalog, &out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "\"status\":\"OK\""));
    memoria_mobile_free_buffer(out); out.data = NULL; out.size = 0;

    for (i = 1; i <= 300; ++i) {
        snprintf(json, sizeof(json),
                 "{\"episode_id\":\"restart-%d\",\"session_id\":\"product\",\"role\":\"user\","
                 "\"text\":\"raw product episode %d\",\"event_type\":\"restart\","
                 "\"topics_csv\":\"raw\",\"order\":%d}",
                 i, i, i);
        CHECK(call_json(memoria_mobile_store_episode_json, h, json, &out) == MEMORIA_MOBILE_OK);
        memoria_mobile_free_buffer(out); out.data = NULL; out.size = 0;
    }

    CHECK(memoria_mobile_flush(h) == MEMORIA_MOBILE_OK);
    memoria_mobile_close(h); h = NULL;

    CHECK(memoria_mobile_open(dir, org, &h) == MEMORIA_MOBILE_OK);
    CHECK(call_json(memoria_mobile_export_snapshot_json, h,
        "{\"turn_offset\":0,\"turn_limit\":1,\"episode_offset\":250,\"episode_limit\":64}", &out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "\"episodes\":300"));
    CHECK(contains(out, "\"episode_id\":\"restart-251\""));
    CHECK(contains(out, "\"episode_id\":\"restart-300\""));
    memoria_mobile_free_buffer(out);

    memoria_mobile_close(h);
    (void)system("rm -rf ./tmp-mobile-shared-bdr-reopen");
    return 0;
}
