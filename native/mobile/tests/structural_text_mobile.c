#include "memoria_mobile.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CHECK(expr) do { if (!(expr)) { fprintf(stderr, "CHECK failed: %s (%s:%d)\n", #expr, __FILE__, __LINE__); return 1; } } while (0)

static memoria_mobile_status call_observe(
    memoria_mobile_handle *h,
    const char *json,
    memoria_mobile_buffer *out
) {
    memoria_mobile_buffer req = {
        (const uint8_t *)json,
        strlen(json)
    };
    return memoria_mobile_observe_structural_text_json(h, req, out);
}

static memoria_mobile_status call_resolve(
    memoria_mobile_handle *h,
    const char *json,
    memoria_mobile_buffer *out
) {
    memoria_mobile_buffer req = {
        (const uint8_t *)json,
        strlen(json)
    };
    return memoria_mobile_resolve_structural_text_json(h, req, out);
}

static int contains(memoria_mobile_buffer out, const char *needle) {
    return out.data && strstr((const char *)out.data, needle) != NULL;
}

static int assert_resolve(memoria_mobile_handle *h) {
    memoria_mobile_buffer out = {0};
    CHECK(call_resolve(
        h,
        "{\"query\":\"Qual é o nome do meu gato?\","
        "\"hierarchy_id\":\"offia:session-1\",\"limit\":3}",
        &out
    ) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "\"status\":\"HIT\""));
    CHECK(contains(out, "Meu gato se chama Alt"));
    CHECK(contains(out, "\"semantic_projection\":false"));
    CHECK(contains(out, "\"observation_count\":3"));
    memoria_mobile_free_buffer(out);
    return 0;
}

int main(void) {
    const char *dir = "./tmp-mobile-structural-text";
    memoria_mobile_handle *h = NULL;
    memoria_mobile_buffer out = {0};

#if defined(_WIN32)
    (void)system("rmdir /S /Q .\\tmp-mobile-structural-text >NUL 2>NUL");
#else
    (void)system("rm -rf ./tmp-mobile-structural-text");
#endif

    CHECK(memoria_mobile_open(dir, "org-offia-v2", &h) == MEMORIA_MOBILE_OK);

    CHECK(call_observe(
        h,
        "{\"text\":\"Meu gato se chama Alt\","
        "\"hierarchy_id\":\"offia:session-1\","
        "\"source_id\":\"offia:user\","
        "\"source_kind\":\"user\",\"sequence\":0}",
        &out
    ) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "\"duplicate\":false"));
    CHECK(contains(out, "\"observation_count\":1"));
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};

    CHECK(call_observe(
        h,
        "{\"text\":\"Meu gato se chama Alt\","
        "\"hierarchy_id\":\"offia:session-1\","
        "\"source_id\":\"offia:user\","
        "\"source_kind\":\"user\",\"sequence\":1}",
        &out
    ) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "\"observation_count\":2"));
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};

    CHECK(call_observe(
        h,
        "{\"text\":\"Meu cachorro se chama Rex\","
        "\"hierarchy_id\":\"offia:session-1\","
        "\"source_id\":\"offia:user\","
        "\"source_kind\":\"user\",\"sequence\":2}",
        &out
    ) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "\"observation_count\":3"));
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};

    /* Exact replay is idempotent and must not reinforce again. */
    CHECK(call_observe(
        h,
        "{\"text\":\"Meu gato se chama Alt\","
        "\"hierarchy_id\":\"offia:session-1\","
        "\"source_id\":\"offia:user\","
        "\"source_kind\":\"user\",\"sequence\":1}",
        &out
    ) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "\"duplicate\":true"));
    CHECK(contains(out, "\"observation_count\":3"));
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};

    CHECK(assert_resolve(h) == 0);

    /* Resolve is read-only: repeated queries cannot grow the observation log. */
    CHECK(assert_resolve(h) == 0);

    CHECK(memoria_mobile_flush(h) == MEMORIA_MOBILE_OK);
    memoria_mobile_close(h);
    h = NULL;

    /* Public ABI must recover the same structural memory after cold reopen. */
    CHECK(memoria_mobile_open(dir, "org-offia-v2", &h) == MEMORIA_MOBILE_OK);
    CHECK(assert_resolve(h) == 0);

    memoria_mobile_close(h);

#if defined(_WIN32)
    (void)system("rmdir /S /Q .\\tmp-mobile-structural-text >NUL 2>NUL");
#else
    (void)system("rm -rf ./tmp-mobile-structural-text");
#endif
    return 0;
}
