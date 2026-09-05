#include "concept_relation_anchor_extractor.h"

#include <ctype.h>
#include <string.h>

static int ascii_ci_equal_n(const char *a, const char *b, size_t n) {
    size_t i;
    for (i = 0; i < n; ++i) {
        unsigned char ca = (unsigned char)a[i];
        unsigned char cb = (unsigned char)b[i];
        if (tolower(ca) != tolower(cb)) return 0;
    }
    return 1;
}

static const char *find_ci(const char *text, const char *needle) {
    size_t n;
    const char *p;
    if (!text || !needle || !*needle) return NULL;
    n = strlen(needle);
    for (p = text; *p; ++p)
        if (strlen(p) >= n && ascii_ci_equal_n(p, needle, n)) return p;
    return NULL;
}

static void trim_copy(const char *start, const char *end, char *out, size_t cap) {
    size_t n;
    while (start < end && isspace((unsigned char)*start)) ++start;
    while (end > start && isspace((unsigned char)end[-1])) --end;
    while (end > start && (end[-1] == '?' || end[-1] == '.' || end[-1] == '!' || end[-1] == ',' || end[-1] == ';')) --end;
    while (start < end && (*start == '"' || *start == '\'')) ++start;
    while (end > start && (end[-1] == '"' || end[-1] == '\'')) --end;
    n = (size_t)(end - start);
    if (n >= cap) n = cap - 1u;
    memcpy(out, start, n);
    out[n] = 0;
}

static int nonempty_distinct(const char *a, const char *b) {
    return a && b && a[0] && b[0] && strcmp(a, b) != 0;
}

static int extract_between(const char *query, const char *prefix, const char *joiner, char *source, size_t source_cap, char *target, size_t target_cap) {
    const char *start, *mid, *end;
    start = find_ci(query, prefix);
    if (!start) return 0;
    start += strlen(prefix);
    mid = find_ci(start, joiner);
    if (!mid) return 0;
    end = query + strlen(query);
    trim_copy(start, mid, source, source_cap);
    trim_copy(mid + strlen(joiner), end, target, target_cap);
    return nonempty_distinct(source, target);
}

static int extract_to(const char *query, const char *prefix, const char *joiner, char *source, size_t source_cap, char *target, size_t target_cap) {
    const char *start, *mid, *end;
    start = find_ci(query, prefix);
    if (!start) return 0;
    start += strlen(prefix);
    mid = find_ci(start, joiner);
    if (!mid) return 0;
    end = query + strlen(query);
    trim_copy(start, mid, source, source_cap);
    trim_copy(mid + strlen(joiner), end, target, target_cap);
    return nonempty_distinct(source, target);
}

memoria_relation_anchor_status memoria_relation_anchor_extract(
    const char *query,
    char *source,
    size_t source_cap,
    char *target,
    size_t target_cap
) {
    if (!query || !source || !target || source_cap == 0 || target_cap == 0)
        return MEMORIA_RELATION_ANCHOR_INVALID;
    source[0] = 0;
    target[0] = 0;

    if (extract_between(query, "relation between ", " and ", source, source_cap, target, target_cap) ||
        extract_between(query, "relationship between ", " and ", source, source_cap, target, target_cap) ||
        extract_between(query, "relação entre ", " e ", source, source_cap, target, target_cap) ||
        extract_between(query, "relacao entre ", " e ", source, source_cap, target, target_cap) ||
        extract_to(query, "how is ", " related to ", source, source_cap, target, target_cap) ||
        extract_to(query, "como ", " se relaciona com ", source, source_cap, target, target_cap))
        return MEMORIA_RELATION_ANCHOR_HIT;

    source[0] = 0;
    target[0] = 0;
    return MEMORIA_RELATION_ANCHOR_UNRESOLVED;
}
