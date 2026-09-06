#ifndef MEMORIA_CONCEPT_RELATION_COLLECTION_QUERY_H
#define MEMORIA_CONCEPT_RELATION_COLLECTION_QUERY_H

#include <ctype.h>
#include <stddef.h>
#include <string.h>

typedef enum memoria_collection_query_status {
    MEMORIA_COLLECTION_QUERY_INVALID = -1,
    MEMORIA_COLLECTION_QUERY_UNRESOLVED = 0,
    MEMORIA_COLLECTION_QUERY_HIT = 1
} memoria_collection_query_status;

static int memoria_collection_ci_equal_n(const char *a, const char *b, size_t n) {
    size_t i;
    for (i = 0; i < n; ++i)
        if (tolower((unsigned char)a[i]) != tolower((unsigned char)b[i])) return 0;
    return 1;
}

static const char *memoria_collection_find_ci(const char *text, const char *needle) {
    size_t n;
    const char *p;
    if (!text || !needle || !*needle) return NULL;
    n = strlen(needle);
    for (p = text; *p; ++p)
        if (strlen(p) >= n && memoria_collection_ci_equal_n(p, needle, n)) return p;
    return NULL;
}

static void memoria_collection_trim_copy(const char *start, const char *end, char *out, size_t cap) {
    size_t n;
    while (start < end && isspace((unsigned char)*start)) ++start;
    while (end > start && isspace((unsigned char)end[-1])) --end;
    while (end > start && (end[-1] == '?' || end[-1] == '.' || end[-1] == '!' || end[-1] == ',' || end[-1] == ';')) --end;
    n = (size_t)(end - start);
    if (n >= cap) n = cap - 1u;
    memcpy(out, start, n);
    out[n] = 0;
}

static void memoria_collection_singularize_simple(char *value) {
    size_t n;
    if (!value) return;
    n = strlen(value);
    if (n > 3u && (value[n - 1u] == 's' || value[n - 1u] == 'S')) value[n - 1u] = 0;
}

static int memoria_collection_extract_between(
    const char *query,
    const char *prefix,
    const char *suffix,
    char *type_surface,
    size_t cap
) {
    const char *start, *end;
    start = memoria_collection_find_ci(query, prefix);
    if (!start) return 0;
    start += strlen(prefix);
    end = memoria_collection_find_ci(start, suffix);
    if (!end) return 0;
    memoria_collection_trim_copy(start, end, type_surface, cap);
    if (!type_surface[0]) return 0;
    memoria_collection_singularize_simple(type_surface);
    return type_surface[0] != 0;
}

static inline memoria_collection_query_status memoria_collection_query_extract(
    const char *query,
    char *type_surface,
    size_t type_cap
) {
    if (!query || !type_surface || !type_cap) return MEMORIA_COLLECTION_QUERY_INVALID;
    type_surface[0] = 0;

    if (memoria_collection_extract_between(query, "quais ", " você conhece", type_surface, type_cap) ||
        memoria_collection_extract_between(query, "quais ", " voce conhece", type_surface, type_cap) ||
        memoria_collection_extract_between(query, "que ", " você conhece", type_surface, type_cap) ||
        memoria_collection_extract_between(query, "que ", " voce conhece", type_surface, type_cap) ||
        memoria_collection_extract_between(query, "which ", " do you know", type_surface, type_cap) ||
        memoria_collection_extract_between(query, "what ", " do you know", type_surface, type_cap))
        return MEMORIA_COLLECTION_QUERY_HIT;

    type_surface[0] = 0;
    return MEMORIA_COLLECTION_QUERY_UNRESOLVED;
}

#endif
