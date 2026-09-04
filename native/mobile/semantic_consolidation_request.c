#include "semantic_consolidation_request.h"

#include <stdint.h>
#include <stdio.h>
#include <string.h>

static uint64_t fnv1a(uint64_t h, const char *s) {
    const unsigned char *p = (const unsigned char *)(s ? s : "");
    while (*p) { h ^= (uint64_t)*p++; h *= UINT64_C(1099511628211); }
    h ^= UINT64_C(255); h *= UINT64_C(1099511628211);
    return h;
}

static int append_json_string(char *out, size_t cap, size_t *pos, const char *s) {
    const unsigned char *p = (const unsigned char *)(s ? s : "");
    if (!out || !pos || *pos >= cap) return 0;
    if (*pos + 1 >= cap) return 0;
    out[(*pos)++] = '"';
    while (*p) {
        const char *esc = NULL;
        char raw[2] = {(char)*p, 0};
        switch (*p) {
            case '"': esc = "\\\""; break;
            case '\\': esc = "\\\\"; break;
            case '\n': esc = "\\n"; break;
            case '\r': esc = "\\r"; break;
            case '\t': esc = "\\t"; break;
            default: esc = raw; break;
        }
        {
            size_t n = strlen(esc);
            if (*pos + n + 1 >= cap) return 0;
            memcpy(out + *pos, esc, n);
            *pos += n;
        }
        ++p;
    }
    out[(*pos)++] = '"';
    out[*pos] = 0;
    return 1;
}

static int append_raw(char *out, size_t cap, size_t *pos, const char *s) {
    size_t n = strlen(s);
    if (*pos + n >= cap) return 0;
    memcpy(out + *pos, s, n);
    *pos += n;
    out[*pos] = 0;
    return 1;
}

int memoria_semantic_consolidation_request_json(
    const memoria_semantic_candidate *candidate,
    long order,
    char *out,
    size_t out_capacity
) {
    uint64_t hash = UINT64_C(14695981039346656037);
    char memory_id[64];
    char text[MEMORIA_SEMANTIC_CONSOLIDATION_TEXT_CAP * 2 + MEMORIA_SEMANTIC_CONSOLIDATION_PREDICATE_CAP + 4];
    char numeric[96];
    size_t i, pos = 0;
    int n;

    if (!candidate || !out || out_capacity < 2 || candidate->support_count < 2) return 0;
    hash = fnv1a(hash, candidate->namespace_id);
    hash = fnv1a(hash, candidate->subject);
    hash = fnv1a(hash, candidate->predicate);
    hash = fnv1a(hash, candidate->object);
    for (i = 0; i < candidate->support_count; ++i)
        hash = fnv1a(hash, candidate->support_memory_ids[i]);

    snprintf(memory_id, sizeof(memory_id), "semantic:%016llx", (unsigned long long)hash);
    n = snprintf(text, sizeof(text), "%s %s %s", candidate->subject, candidate->predicate, candidate->object);
    if (n < 0 || (size_t)n >= sizeof(text)) return 0;

    out[0] = 0;
    if (!append_raw(out, out_capacity, &pos, "{\"role\":\"assistant\",\"text\":")) return 0;
    if (!append_json_string(out, out_capacity, &pos, text)) return 0;
    if (!append_raw(out, out_capacity, &pos, ",\"memory_id\":")) return 0;
    if (!append_json_string(out, out_capacity, &pos, memory_id)) return 0;
    if (!append_raw(out, out_capacity, &pos, ",\"namespace\":")) return 0;
    if (!append_json_string(out, out_capacity, &pos, candidate->namespace_id)) return 0;
    if (!append_raw(out, out_capacity, &pos, ",\"source_type\":\"derived_relation\",\"source_authority\":")) return 0;
    snprintf(numeric, sizeof(numeric), "%.17g,\"order\":%ld,\"parent_memory_ids\":[", candidate->confidence, order);
    if (!append_raw(out, out_capacity, &pos, numeric)) return 0;
    for (i = 0; i < candidate->support_count; ++i) {
        if (i && !append_raw(out, out_capacity, &pos, ",")) return 0;
        if (!append_json_string(out, out_capacity, &pos, candidate->support_memory_ids[i])) return 0;
    }
    if (!append_raw(out, out_capacity, &pos, "]}")) return 0;
    return 1;
}
