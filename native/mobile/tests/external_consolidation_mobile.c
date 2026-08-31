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

static int first_id(memoria_mobile_buffer b, char *out, size_t cap) {
    const char *marker = "\"stored_memory_ids\":[\"";
    const char *p, *q;
    size_t n;
    if (!b.data || !out || !cap) return 0;
    p = strstr((const char *)b.data, marker);
    if (!p) return 0;
    p += strlen(marker);
    q = strchr(p, '"');
    if (!q) return 0;
    n = (size_t)(q - p);
    if (n + 1u > cap) return 0;
    memcpy(out, p, n); out[n] = 0;
    return 1;
}

static memoria_mobile_status learn(memoria_mobile_handle *h, const char *json, memoria_mobile_buffer *out) {
    return memoria_mobile_learn_external_knowledge_json(h, buf(json), out);
}

static memoria_mobile_status consolidation(memoria_mobile_handle *h, const char *id, memoria_mobile_buffer *out) {
    char request[512];
    snprintf(request, sizeof(request), "{\"memory_id\":\"%s\",\"namespace\":\"\"}", id);
    return memoria_mobile_inspect_external_consolidation_json(h, buf(request), out);
}

int main(void) {
    const char *dir = "./tmp-mobile-external-consolidation";
    memoria_mobile_handle *h = NULL;
    memoria_mobile_buffer out = {0};
    char id[128] = {0};

    (void)system("rm -rf ./tmp-mobile-external-consolidation");
    CHECK(memoria_mobile_open(dir, "org-consolidation", &h) == MEMORIA_MOBILE_OK);

    CHECK(learn(h,
        "{\"content\":\"atlas code is 7319\",\"source_url\":\"https://one.example/a\","
        "\"source_domain\":\"one.example\",\"source_title\":\"Atlas A\","
        "\"acquired_time\":\"2026-08-31T15:00:00Z\",\"import_kind\":\"imported\","
        "\"validation_confidence\":0.91}", &out) == MEMORIA_MOBILE_OK);
    CHECK(first_id(out, id, sizeof(id)));
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};

    CHECK(consolidation(h, id, &out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "\"evidence_state\":\"raw\""));
    CHECK(contains(out, "\"observed_sources\":1"));
    CHECK(contains(out, "\"independent_domains\":1"));
    CHECK(contains(out, "\"semantic_conflict_checked\":true"));
    CHECK(contains(out, "\"semantic_conflict\":false"));
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};

    /* A second URL from the same domain is more evidence, but not independent corroboration. */
    CHECK(learn(h,
        "{\"content\":\"atlas code is 7319\",\"source_url\":\"https://one.example/b\","
        "\"source_domain\":\"ONE.EXAMPLE\",\"source_title\":\"Atlas A2\","
        "\"acquired_time\":\"2026-08-31T15:01:00Z\",\"import_kind\":\"imported\","
        "\"validation_confidence\":0.95}", &out) == MEMORIA_MOBILE_OK);
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};
    CHECK(consolidation(h, id, &out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "\"evidence_state\":\"raw\""));
    CHECK(contains(out, "\"observed_sources\":2"));
    CHECK(contains(out, "\"independent_domains\":1"));
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};

    CHECK(learn(h,
        "{\"content\":\"atlas code is 7319\",\"source_url\":\"https://two.example/a\","
        "\"source_domain\":\"two.example\",\"source_title\":\"Atlas B\","
        "\"acquired_time\":\"2026-08-31T15:02:00Z\",\"import_kind\":\"imported\","
        "\"validation_confidence\":0.88}", &out) == MEMORIA_MOBILE_OK);
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};
    CHECK(consolidation(h, id, &out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "\"evidence_state\":\"corroborated\""));
    CHECK(contains(out, "\"observed_sources\":3"));
    CHECK(contains(out, "\"independent_domains\":2"));
    CHECK(contains(out, "\"qualifying_independent_domains\":2"));
    CHECK(contains(out, "\"durable_basis\":\"external_public_provenance\""));
    CHECK(contains(out, "\"semantic_conflict\":false"));
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};

    /* Contradictory public relation must override corroboration conservatively. */
    CHECK(learn(h,
        "{\"content\":\"atlas code is 9999\",\"source_url\":\"https://three.example/a\","
        "\"source_domain\":\"three.example\",\"source_title\":\"Atlas C\","
        "\"acquired_time\":\"2026-08-31T15:03:00Z\",\"import_kind\":\"imported\","
        "\"validation_confidence\":0.93}", &out) == MEMORIA_MOBILE_OK);
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};
    CHECK(consolidation(h, id, &out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "\"evidence_state\":\"conflict\""));
    CHECK(contains(out, "\"semantic_conflict_checked\":true"));
    CHECK(contains(out, "\"semantic_conflict\":true"));
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};

    CHECK(memoria_mobile_flush(h) == MEMORIA_MOBILE_OK);
    memoria_mobile_close(h); h = NULL;

    /* Both corroboration and the contradictory relation are reconstructed from durable state. */
    CHECK(memoria_mobile_open(dir, "org-consolidation", &h) == MEMORIA_MOBILE_OK);
    CHECK(consolidation(h, id, &out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "\"evidence_state\":\"conflict\""));
    CHECK(contains(out, "\"observed_sources\":3"));
    CHECK(contains(out, "\"independent_domains\":2"));
    CHECK(contains(out, "\"semantic_conflict\":true"));
    memoria_mobile_free_buffer(out);

    memoria_mobile_close(h);
    (void)system("rm -rf ./tmp-mobile-external-consolidation");
    return 0;
}
