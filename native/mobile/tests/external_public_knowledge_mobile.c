#include "memoria_mobile.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CHECK(expr) do { if (!(expr)) { fprintf(stderr,"CHECK failed: %s (%s:%d)\n",#expr,__FILE__,__LINE__); return 1; } } while (0)

static int contains(memoria_mobile_buffer b, const char *needle) {
    return b.data && needle && strstr((const char *)b.data, needle) != NULL;
}

static memoria_mobile_status external_learn(memoria_mobile_handle *h, const char *json, memoria_mobile_buffer *out) {
    memoria_mobile_buffer in = {(const uint8_t *)json, strlen(json)};
    return memoria_mobile_learn_external_knowledge_json(h, in, out);
}

static memoria_mobile_status personal_learn(memoria_mobile_handle *h, const char *json, memoria_mobile_buffer *out) {
    memoria_mobile_buffer in = {(const uint8_t *)json, strlen(json)};
    return memoria_mobile_learn_turn_json(h, in, out);
}

static memoria_mobile_status resolve(memoria_mobile_handle *h, const char *json, memoria_mobile_buffer *out) {
    memoria_mobile_buffer in = {(const uint8_t *)json, strlen(json)};
    return memoria_mobile_resolve_context_json(h, in, out);
}

static memoria_mobile_status inspect_external(memoria_mobile_handle *h, const char *memory_id, memoria_mobile_buffer *out) {
    char json[512];
    memoria_mobile_buffer in;
    snprintf(json, sizeof(json), "{\"memory_id\":\"%s\",\"namespace\":\"\"}", memory_id);
    in.data = (const uint8_t *)json;
    in.size = strlen(json);
    return memoria_mobile_inspect_external_knowledge_json(h, in, out);
}

static int first_stored_id(memoria_mobile_buffer b, char *out, size_t cap) {
    const char *marker = "\"stored_memory_ids\":[\"";
    const char *p, *q;
    size_t n;
    if (!b.data || !out || cap == 0) return 0;
    p = strstr((const char *)b.data, marker);
    if (!p) return 0;
    p += strlen(marker);
    q = strchr(p, '"');
    if (!q) return 0;
    n = (size_t)(q - p);
    if (n + 1u > cap) return 0;
    memcpy(out, p, n);
    out[n] = 0;
    return 1;
}

int main(void) {
    memoria_mobile_handle *h = NULL;
    memoria_mobile_buffer out = {0};
    char public_id[128] = {0};
    char derived_id[128] = {0};
    char conflict_a_id[128] = {0};
    char conflict_b_id[128] = {0};
    char request[2048];

    (void)system("rm -rf ./tmp-mobile-external-public");
    CHECK(memoria_mobile_open("./tmp-mobile-external-public", "org-external", &h) == MEMORIA_MOBILE_OK);

    /* Required provenance is semantic, not a user assertion. */
    CHECK(external_learn(h,
        "{\"content\":\"orbital test code is 7319\",\"source_class\":\"external_public\","
        "\"source_url\":\"https://example.org/fact-a\",\"source_domain\":\"example.org\","
        "\"source_title\":\"Public Fact A\",\"acquired_time\":\"2026-08-30T04:40:00Z\","
        "\"source_excerpt\":\"reference excerpt\",\"provider_id\":\"test-provider\","
        "\"import_kind\":\"synthesized\",\"validation_confidence\":0.91}", &out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "\"knowledge_class\":\"external_public\""));
    CHECK(contains(out, "\"source_type\":\"external_import\""));
    CHECK(contains(out, "\"deduplicated\":false"));
    CHECK(contains(out, "\"federation_eligible\":false"));
    CHECK(first_stored_id(out, public_id, sizeof(public_id)));
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};

    /* Android/consumer serializers may escape forward slashes and quotes. */
    CHECK(external_learn(h,
        "{\"content\":\"android says \\\"ocean\\\" is public\","
        "\"source_class\":\"external_public\","
        "\"source_url\":\"https:\\/\\/example.org\\/android\","
        "\"source_domain\":\"example.org\",\"source_title\":\"Android \\\"Public\\\" Source\","
        "\"acquired_time\":\"2026-08-30T04:40:30Z\",\"import_kind\":\"imported\"}", &out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "\"knowledge_class\":\"external_public\""));
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};

    CHECK(inspect_external(h, public_id, &out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "https://example.org/fact-a"));
    CHECK(contains(out, "\"source_domain\":\"example.org\""));
    CHECK(contains(out, "\"source_title\":\"Public Fact A\""));
    CHECK(contains(out, "2026-08-30T04:40:00Z"));
    CHECK(contains(out, "\"source_count\":1"));
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};

    /* Same fact + same source is deterministic and does not duplicate memory. */
    CHECK(external_learn(h,
        "{\"content\":\"orbital test code is 7319\",\"source_url\":\"https://example.org/fact-a\","
        "\"source_domain\":\"example.org\",\"source_title\":\"Public Fact A\","
        "\"acquired_time\":\"2026-08-30T04:41:00Z\",\"import_kind\":\"synthesized\"}", &out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, public_id));
    CHECK(contains(out, "\"deduplicated\":true"));
    CHECK(contains(out, "\"source_attached\":false"));
    CHECK(contains(out, "\"source_count\":1"));
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};

    /* Same semantic fact + independent source adds evidence, not another fact. */
    CHECK(external_learn(h,
        "{\"content\":\"orbital test code is 7319\",\"source_url\":\"https://docs.example.net/fact-b\","
        "\"source_domain\":\"docs.example.net\",\"source_title\":\"Independent Fact B\","
        "\"acquired_time\":\"2026-08-30T04:42:00Z\",\"import_kind\":\"imported\","
        "\"validation_confidence\":0.88}", &out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, public_id));
    CHECK(contains(out, "\"deduplicated\":true"));
    CHECK(contains(out, "\"source_attached\":true"));
    CHECK(contains(out, "\"source_count\":2"));
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};

    CHECK(inspect_external(h, public_id, &out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "https://example.org/fact-a"));
    CHECK(contains(out, "https://docs.example.net/fact-b"));
    CHECK(contains(out, "\"source_count\":2"));
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};

    /* Derived public knowledge must remain rooted only in public parents. */
    snprintf(request, sizeof(request),
        "{\"content\":\"derived orbital status is verified\",\"source_url\":\"https://example.org/derived\","
        "\"source_domain\":\"example.org\",\"source_title\":\"Derived synthesis\","
        "\"acquired_time\":\"2026-08-30T04:43:00Z\",\"import_kind\":\"derived\","
        "\"parent_memory_ids\":[\"%s\"]}", public_id);
    CHECK(external_learn(h, request, &out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "\"source_type\":\"derived_relation\""));
    CHECK(first_stored_id(out, derived_id, sizeof(derived_id)));
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};
    CHECK(inspect_external(h, derived_id, &out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "\"import_kind\":\"derived\""));
    CHECK(contains(out, public_id));
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};

    /* A private/user memory cannot become a public derived parent implicitly. */
    CHECK(personal_learn(h,
        "{\"role\":\"user\",\"text\":\"private marker is 44\",\"memory_id\":\"private-root\","
        "\"namespace\":\"\",\"source_type\":\"user_assertion\",\"source_authority\":1.0}", &out) == MEMORIA_MOBILE_OK);
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};
    CHECK(external_learn(h,
        "{\"content\":\"public leak test is 44\",\"source_url\":\"https://example.org/leak\","
        "\"source_domain\":\"example.org\",\"source_title\":\"Leak test\","
        "\"acquired_time\":\"2026-08-30T04:44:00Z\",\"import_kind\":\"derived\","
        "\"parent_memory_ids\":[\"private-root\"]}", &out) == MEMORIA_MOBILE_INVALID_ARGUMENT);
    if (out.data) memoria_mobile_free_buffer(out);
    out = (memoria_mobile_buffer){0};

    /* External knowledge cannot overwrite stronger personal authority. */
    CHECK(personal_learn(h,
        "{\"role\":\"user\",\"text\":\"device voltage is 24 V\",\"memory_id\":\"personal-voltage\","
        "\"namespace\":\"\",\"source_type\":\"user_assertion\",\"source_authority\":1.0}", &out) == MEMORIA_MOBILE_OK);
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};
    CHECK(external_learn(h,
        "{\"content\":\"device voltage is 30 V\",\"source_url\":\"https://example.org/device\","
        "\"source_domain\":\"example.org\",\"source_title\":\"Device public spec\","
        "\"acquired_time\":\"2026-08-30T04:45:00Z\",\"import_kind\":\"imported\"}", &out) == MEMORIA_MOBILE_OK);
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};
    CHECK(resolve(h, "{\"query\":\"device voltage\",\"namespace\":\"\"}", &out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "24 V"));
    CHECK(!contains(out, "30 V"));
    CHECK(contains(out, "\"source_type\":\"user_assertion\""));
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};

    /* Contradictory public sources stay separately auditable and resolve conservatively. */
    CHECK(external_learn(h,
        "{\"content\":\"planet code is alpha\",\"source_url\":\"https://a.example/planet\","
        "\"source_domain\":\"a.example\",\"source_title\":\"Planet A\","
        "\"acquired_time\":\"2026-08-30T04:46:00Z\",\"import_kind\":\"imported\"}", &out) == MEMORIA_MOBILE_OK);
    CHECK(first_stored_id(out, conflict_a_id, sizeof(conflict_a_id)));
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};
    CHECK(external_learn(h,
        "{\"content\":\"planet code is beta\",\"source_url\":\"https://b.example/planet\","
        "\"source_domain\":\"b.example\",\"source_title\":\"Planet B\","
        "\"acquired_time\":\"2026-08-30T04:47:00Z\",\"import_kind\":\"imported\"}", &out) == MEMORIA_MOBILE_OK);
    CHECK(first_stored_id(out, conflict_b_id, sizeof(conflict_b_id)));
    CHECK(strcmp(conflict_a_id, conflict_b_id) != 0);
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};
    CHECK(inspect_external(h, conflict_a_id, &out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "https://a.example/planet"));
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};
    CHECK(inspect_external(h, conflict_b_id, &out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "https://b.example/planet"));
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};
    CHECK(resolve(h, "{\"query\":\"planet code\",\"namespace\":\"\"}", &out) == MEMORIA_MOBILE_UNRESOLVED);
    CHECK(contains(out, "\"status\":\"UNRESOLVED\""));
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};

    /* UTF-8 provenance must remain byte-exact through BDR. */
    CHECK(external_learn(h,
        "{\"content\":\"cidade teste is São Paulo\",\"source_url\":\"https://example.org/cidade\","
        "\"source_domain\":\"example.org\",\"source_title\":\"Informação pública — São Paulo\","
        "\"acquired_time\":\"2026-08-30T04:48:00Z\",\"import_kind\":\"imported\"}", &out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "São Paulo"));
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};

    /* Validation is fail-closed for incomplete/malformed provenance. */
    CHECK(external_learn(h,
        "{\"content\":\"bad fact is 1\",\"source_url\":\"https://example.org/bad\","
        "\"source_domain\":\"example.org\",\"acquired_time\":\"2026-08-30T04:49:00Z\"}", &out) == MEMORIA_MOBILE_INVALID_ARGUMENT);
    if (out.data) memoria_mobile_free_buffer(out);
    out = (memoria_mobile_buffer){0};

    CHECK(memoria_mobile_flush(h) == MEMORIA_MOBILE_OK);
    memoria_mobile_close(h); h = NULL;

    /* Fresh process, no network: semantic recall and full source provenance survive. */
    CHECK(memoria_mobile_open("./tmp-mobile-external-public", "org-external", &h) == MEMORIA_MOBILE_OK);
    CHECK(resolve(h, "{\"query\":\"orbital test code\",\"namespace\":\"\"}", &out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "7319"));
    CHECK(contains(out, "\"source_type\":\"external_import\""));
    CHECK(contains(out, "\"knowledge_class\":\"external_public\""));
    CHECK(contains(out, "\"external_public_provenance\""));
    CHECK(contains(out, "https://example.org/fact-a"));
    CHECK(contains(out, "https://docs.example.net/fact-b"));
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};

    CHECK(inspect_external(h, public_id, &out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "\"source_count\":2"));
    CHECK(contains(out, "Public Fact A"));
    CHECK(contains(out, "Independent Fact B"));
    memoria_mobile_free_buffer(out);

    memoria_mobile_close(h);
    (void)system("rm -rf ./tmp-mobile-external-public");
    return 0;
}
