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

static memoria_mobile_status inspect(memoria_mobile_handle *h, const char *id, memoria_mobile_buffer *out) {
    char request[512];
    snprintf(request, sizeof(request),
        "{\"memory_id\":\"%s\",\"namespace\":\"\",\"source_url\":\"https://example.org/atlas\"}", id);
    return memoria_mobile_inspect_evidence_metrics_json(h, buf(request), out);
}

int main(void) {
    const char *dir = "./tmp-mobile-evidence-metrics";
    memoria_mobile_handle *h = NULL;
    memoria_mobile_buffer out = {0};
    char id[128] = {0};

    (void)system("rm -rf ./tmp-mobile-evidence-metrics");
    CHECK(memoria_mobile_open(dir, "org-evidence-metrics", &h) == MEMORIA_MOBILE_OK);

    CHECK(memoria_mobile_learn_external_knowledge_json(h, buf(
        "{\"content\":\"atlas code is 7319\","
        "\"source_url\":\"https://example.org/atlas\",\"source_domain\":\"example.org\","
        "\"source_title\":\"Atlas\",\"acquired_time\":\"2026-09-01T04:00:00Z\","
        "\"import_kind\":\"imported\",\"validation_confidence\":0.91,"
        "\"source_authority\":0.72,\"retrieval_relevance\":0.83,"
        "\"semantic_confidence\":0.88,\"freshness\":0.64}"), &out) == MEMORIA_MOBILE_OK);
    CHECK(first_id(out, id, sizeof(id)));
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};

    CHECK(inspect(h, id, &out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "\"source_authority\":0.72"));
    CHECK(contains(out, "\"retrieval_relevance\":0.83"));
    CHECK(contains(out, "\"semantic_confidence\":0.88"));
    CHECK(contains(out, "\"freshness\":0.64"));
    CHECK(contains(out, "\"legacy_validation_confidence_preserved\":true"));
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};

    CHECK(memoria_mobile_flush(h) == MEMORIA_MOBILE_OK);
    memoria_mobile_close(h); h = NULL;

    CHECK(memoria_mobile_open(dir, "org-evidence-metrics", &h) == MEMORIA_MOBILE_OK);
    CHECK(inspect(h, id, &out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "\"source_authority\":0.72"));
    CHECK(contains(out, "\"retrieval_relevance\":0.83"));
    CHECK(contains(out, "\"semantic_confidence\":0.88"));
    CHECK(contains(out, "\"freshness\":0.64"));
    memoria_mobile_free_buffer(out);

    memoria_mobile_close(h);
    (void)system("rm -rf ./tmp-mobile-evidence-metrics");
    return 0;
}
