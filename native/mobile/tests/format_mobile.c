#include "memoria_mobile.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CHECK(expr) do { if (!(expr)) { fprintf(stderr,"CHECK failed: %s (%s:%d)\n",#expr,__FILE__,__LINE__); return 1; } } while (0)

static memoria_mobile_status call_json(
    memoria_mobile_status (*fn)(memoria_mobile_handle *, memoria_mobile_buffer, memoria_mobile_buffer *),
    memoria_mobile_handle *h,
    const char *json,
    memoria_mobile_buffer *out
) {
    memoria_mobile_buffer in = {(const uint8_t *)json, strlen(json)};
    return fn(h, in, out);
}

static int contains(memoria_mobile_buffer b, const char *needle) {
    return b.data && strstr((const char *)b.data, needle) != NULL;
}

int main(void) {
    const char *dir = "./tmp-mobile-format";
    memoria_mobile_handle *h = NULL;
    memoria_mobile_buffer out = {0};

    (void)system("rm -rf ./tmp-mobile-format");
    CHECK(memoria_mobile_open(dir, "org-format", &h) == MEMORIA_MOBILE_OK);

    CHECK(call_json(
        memoria_mobile_learn_turn_json,
        h,
        "{\"role\":\"user\",\"text\":\"alpha node is blue\",\"memory_id\":\"u1\",\"order\":1}",
        &out
    ) == MEMORIA_MOBILE_OK);
    memoria_mobile_free_buffer(out); out=(memoria_mobile_buffer){0};

    CHECK(call_json(
        memoria_mobile_store_episode_json,
        h,
        "{\"episode_id\":\"e1\",\"role\":\"user\",\"text\":\"raw page evidence\","
        "\"timestamp\":\"2026-09-21T19:00:00Z\",\"order\":1,\"event_type\":\"web\",\"topics_csv\":\"raw\"}",
        &out
    ) == MEMORIA_MOBILE_OK);
    memoria_mobile_free_buffer(out); out=(memoria_mobile_buffer){0};

    CHECK(call_json(
        memoria_mobile_format_json,
        h,
        "{\"confirm\":\"NO\"}",
        &out
    ) == MEMORIA_MOBILE_INVALID_ARGUMENT);
    CHECK(out.data == NULL);

    CHECK(call_json(
        memoria_mobile_format_json,
        h,
        "{\"confirm\":\"FORMATAR\"}",
        &out
    ) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "\"status\":\"OK\""));
    CHECK(contains(out, "\"removed_turns\":1"));
    CHECK(contains(out, "\"removed_episodes\":1"));
    CHECK(contains(out, "\"wal_preserved\":true"));
    memoria_mobile_free_buffer(out); out=(memoria_mobile_buffer){0};

    CHECK(call_json(
        memoria_mobile_resolve_context_json,
        h,
        "{\"query\":\"alpha node blue\"}",
        &out
    ) == MEMORIA_MOBILE_UNRESOLVED);
    memoria_mobile_free_buffer(out); out=(memoria_mobile_buffer){0};

    CHECK(memoria_mobile_flush(h) == MEMORIA_MOBILE_OK);
    memoria_mobile_close(h); h=NULL;

    CHECK(memoria_mobile_open(dir, "org-format", &h) == MEMORIA_MOBILE_OK);
    CHECK(call_json(
        memoria_mobile_resolve_context_json,
        h,
        "{\"query\":\"alpha node blue\"}",
        &out
    ) == MEMORIA_MOBILE_UNRESOLVED);
    memoria_mobile_free_buffer(out); out=(memoria_mobile_buffer){0};

    CHECK(call_json(
        memoria_mobile_learn_turn_json,
        h,
        "{\"role\":\"user\",\"text\":\"beta node is green\",\"memory_id\":\"u2\",\"order\":1}",
        &out
    ) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "\"durable\":true"));
    memoria_mobile_free_buffer(out); out=(memoria_mobile_buffer){0};

    CHECK(memoria_mobile_flush(h) == MEMORIA_MOBILE_OK);
    memoria_mobile_close(h);
    (void)system("rm -rf ./tmp-mobile-format");
    puts("Memoria mobile logical format PASS");
    return 0;
}
