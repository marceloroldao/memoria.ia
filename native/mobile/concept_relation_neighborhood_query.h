#ifndef MEMORIA_CONCEPT_RELATION_NEIGHBORHOOD_QUERY_H
#define MEMORIA_CONCEPT_RELATION_NEIGHBORHOOD_QUERY_H

#include <ctype.h>
#include <stddef.h>
#include <string.h>

typedef enum memoria_neighborhood_query_status {
    MEMORIA_NEIGHBORHOOD_QUERY_INVALID = -1,
    MEMORIA_NEIGHBORHOOD_QUERY_UNRESOLVED = 0,
    MEMORIA_NEIGHBORHOOD_QUERY_HIT = 1
} memoria_neighborhood_query_status;

static int memoria_neighborhood_ci_equal_n(const char *a, const char *b, size_t n) {
    size_t i;
    for (i = 0; i < n; ++i)
        if (tolower((unsigned char)a[i]) != tolower((unsigned char)b[i])) return 0;
    return 1;
}

static const char *memoria_neighborhood_find_ci(const char *text, const char *needle) {
    size_t n;
    const char *p;
    if (!text || !needle || !*needle) return NULL;
    n = strlen(needle);
    for (p = text; *p; ++p)
        if (strlen(p) >= n && memoria_neighborhood_ci_equal_n(p, needle, n)) return p;
    return NULL;
}

static void memoria_neighborhood_trim_copy(const char *start, const char *end, char *out, size_t cap) {
    size_t n;
    while (start < end && isspace((unsigned char)*start)) ++start;
    while (end > start && isspace((unsigned char)end[-1])) --end;
    while (end > start && (end[-1] == '?' || end[-1] == '.' || end[-1] == '!' || end[-1] == ',' || end[-1] == ';')) --end;
    n = (size_t)(end - start);
    if (n >= cap) n = cap - 1u;
    memcpy(out, start, n);
    out[n] = 0;
}

static int memoria_neighborhood_extract_after(const char *query, const char *prefix, char *source, size_t cap) {
    const char *start = memoria_neighborhood_find_ci(query, prefix);
    const char *end;
    if (!start) return 0;
    start += strlen(prefix);
    end = query + strlen(query);
    memoria_neighborhood_trim_copy(start, end, source, cap);
    return source[0] != 0;
}

static inline memoria_neighborhood_query_status memoria_relation_neighborhood_query_extract(
    const char *query,
    char *source,
    size_t source_cap
) {
    if (!query || !source || source_cap == 0) return MEMORIA_NEIGHBORHOOD_QUERY_INVALID;
    source[0] = 0;
    if (memoria_neighborhood_extract_after(query, "what is related to ", source, source_cap) ||
        memoria_neighborhood_extract_after(query, "what's related to ", source, source_cap) ||
        memoria_neighborhood_extract_after(query, "what connects to ", source, source_cap) ||
        memoria_neighborhood_extract_after(query, "o que está relacionado a ", source, source_cap) ||
        memoria_neighborhood_extract_after(query, "o que esta relacionado a ", source, source_cap) ||
        memoria_neighborhood_extract_after(query, "o que se relaciona com ", source, source_cap) ||
        memoria_neighborhood_extract_after(query, "o que está ligado a ", source, source_cap) ||
        memoria_neighborhood_extract_after(query, "o que esta ligado a ", source, source_cap))
        return MEMORIA_NEIGHBORHOOD_QUERY_HIT;
    source[0] = 0;
    return MEMORIA_NEIGHBORHOOD_QUERY_UNRESOLVED;
}

#endif
