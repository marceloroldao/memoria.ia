#ifndef MEMORIA_CONCEPT_RELATION_ANCHOR_EXTRACTOR_H
#define MEMORIA_CONCEPT_RELATION_ANCHOR_EXTRACTOR_H

#include <ctype.h>
#include <stddef.h>
#include <string.h>

typedef enum memoria_relation_anchor_status {
    MEMORIA_RELATION_ANCHOR_INVALID = -1,
    MEMORIA_RELATION_ANCHOR_UNRESOLVED = 0,
    MEMORIA_RELATION_ANCHOR_HIT = 1
} memoria_relation_anchor_status;

static int memoria_anchor_ascii_ci_equal_n(const char *a, const char *b, size_t n) {
    size_t i;
    for (i = 0; i < n; ++i)
        if (tolower((unsigned char)a[i]) != tolower((unsigned char)b[i])) return 0;
    return 1;
}

static const char *memoria_anchor_find_ci(const char *text, const char *needle) {
    size_t n;
    const char *p;
    if (!text || !needle || !*needle) return NULL;
    n = strlen(needle);
    for (p = text; *p; ++p)
        if (strlen(p) >= n && memoria_anchor_ascii_ci_equal_n(p, needle, n)) return p;
    return NULL;
}

static void memoria_anchor_trim_copy(const char *start, const char *end, char *out, size_t cap) {
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

static int memoria_anchor_nonempty_distinct(const char *a, const char *b) {
    return a && b && a[0] && b[0] && strcmp(a, b) != 0;
}

static int memoria_anchor_extract_pair(
    const char *query,
    const char *prefix,
    const char *joiner,
    char *source,
    size_t source_cap,
    char *target,
    size_t target_cap
) {
    const char *start, *mid, *end;
    start = memoria_anchor_find_ci(query, prefix);
    if (!start) return 0;
    start += strlen(prefix);
    mid = memoria_anchor_find_ci(start, joiner);
    if (!mid) return 0;
    end = query + strlen(query);
    memoria_anchor_trim_copy(start, mid, source, source_cap);
    memoria_anchor_trim_copy(mid + strlen(joiner), end, target, target_cap);
    return memoria_anchor_nonempty_distinct(source, target);
}

static inline memoria_relation_anchor_status memoria_relation_anchor_extract(
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

    if (memoria_anchor_extract_pair(query, "relation between ", " and ", source, source_cap, target, target_cap) ||
        memoria_anchor_extract_pair(query, "relationship between ", " and ", source, source_cap, target, target_cap) ||
        memoria_anchor_extract_pair(query, "relação entre ", " e ", source, source_cap, target, target_cap) ||
        memoria_anchor_extract_pair(query, "relacao entre ", " e ", source, source_cap, target, target_cap) ||
        memoria_anchor_extract_pair(query, "how is ", " related to ", source, source_cap, target, target_cap) ||
        memoria_anchor_extract_pair(query, "is ", " related to ", source, source_cap, target, target_cap) ||
        memoria_anchor_extract_pair(query, "what connects ", " to ", source, source_cap, target, target_cap) ||
        memoria_anchor_extract_pair(query, "como ", " se relaciona com ", source, source_cap, target, target_cap) ||
        memoria_anchor_extract_pair(query, "o que conecta ", " a ", source, source_cap, target, target_cap) ||
        memoria_anchor_extract_pair(query, "o que liga ", " a ", source, source_cap, target, target_cap))
        return MEMORIA_RELATION_ANCHOR_HIT;

    source[0] = 0;
    target[0] = 0;
    return MEMORIA_RELATION_ANCHOR_UNRESOLVED;
}

#endif
