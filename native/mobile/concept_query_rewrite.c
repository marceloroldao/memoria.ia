#include "concept_query_rewrite.h"

#include <stdio.h>
#include <string.h>

static const memoria_concept_record *find_concept(
    const memoria_concept_index *index,
    const char *concept_id,
    const char *namespace_name
) {
    size_t i;
    const char *ns = namespace_name ? namespace_name : "";
    if (!index || !concept_id) return NULL;
    for (i = 0; i < index->concept_count; ++i) {
        const memoria_concept_record *c = &index->concepts[i];
        if (strcmp(c->concept_id, concept_id) == 0 && strcmp(c->namespace_name, ns) == 0) return c;
    }
    return NULL;
}

static int append_text(char *dst, size_t cap, size_t *used, const char *text, int with_space) {
    size_t n;
    if (!dst || !used || !text) return 0;
    n = strlen(text);
    if (*used + n + (with_space ? 1u : 0u) >= cap) return 0;
    if (with_space) dst[(*used)++] = ' ';
    memcpy(dst + *used, text, n);
    *used += n;
    dst[*used] = 0;
    return 1;
}

static int remember_id(memoria_concept_rewrite_result *out, const char *concept_id) {
    size_t i;
    if (!out || !concept_id) return 0;
    for (i = 0; i < out->concept_count; ++i)
        if (strcmp(out->concept_ids[i], concept_id) == 0) return 1;
    if (out->concept_count >= MEMORIA_CONCEPT_QUERY_MAX_IDS) return 0;
    snprintf(out->concept_ids[out->concept_count], MEMORIA_CONCEPT_ID_CAP, "%s", concept_id);
    ++out->concept_count;
    return 1;
}

memoria_concept_rewrite_result memoria_concept_rewrite_query(
    const memoria_concept_index *index,
    const char *namespace_name,
    const char *query,
    size_t max_alias_words
) {
    memoria_concept_rewrite_result out;
    char normalized[MEMORIA_CONCEPT_QUERY_CAP];
    char work[MEMORIA_CONCEPT_QUERY_CAP];
    char *words[128];
    size_t word_count = 0, i = 0, used = 0;
    int changed = 0;

    memset(&out, 0, sizeof(out));
    if (!index || !query || max_alias_words < 1u ||
        !memoria_concept_normalize(query, normalized, sizeof(normalized))) {
        out.status = MEMORIA_CONCEPT_REWRITE_UNRESOLVED;
        out.reason = MEMORIA_CONCEPT_REWRITE_REASON_CAPACITY;
        return out;
    }
    snprintf(out.original_query, sizeof(out.original_query), "%s", query);
    if (!normalized[0]) {
        out.status = MEMORIA_CONCEPT_REWRITE_UNCHANGED;
        out.reason = MEMORIA_CONCEPT_REWRITE_REASON_EMPTY;
        snprintf(out.rewritten_query, sizeof(out.rewritten_query), "%s", query);
        return out;
    }

    snprintf(work, sizeof(work), "%s", normalized);
    {
        char *p = work;
        while (*p && word_count < sizeof(words) / sizeof(words[0])) {
            while (*p == ' ') ++p;
            if (!*p) break;
            words[word_count++] = p;
            while (*p && *p != ' ') ++p;
            if (*p) *p++ = 0;
        }
        if (*p) {
            out.status = MEMORIA_CONCEPT_REWRITE_UNRESOLVED;
            out.reason = MEMORIA_CONCEPT_REWRITE_REASON_CAPACITY;
            return out;
        }
    }

    out.rewritten_query[0] = 0;
    while (i < word_count) {
        size_t width, longest = max_alias_words;
        int matched = 0;
        if (longest > word_count - i) longest = word_count - i;
        for (width = longest; width > 0; --width) {
            char surface[MEMORIA_CONCEPT_SURFACE_CAP];
            size_t j, su = 0;
            memoria_concept_resolution r;
            const memoria_concept_record *concept;
            surface[0] = 0;
            for (j = 0; j < width; ++j) {
                if (!append_text(surface, sizeof(surface), &su, words[i + j], j != 0)) break;
            }
            if (j != width) continue;
            r = memoria_concept_resolve(index, namespace_name, surface);
            if (r.reason == MEMORIA_CONCEPT_REASON_AMBIGUOUS) {
                memoria_concept_resolution contextual = memoria_concept_resolve_with_context(
                    index, namespace_name, surface, query
                );
                if (contextual.status == MEMORIA_CONCEPT_HIT) r = contextual;
                else {
                    out.status = MEMORIA_CONCEPT_REWRITE_UNRESOLVED;
                    out.reason = contextual.reason == MEMORIA_CONCEPT_REASON_AMBIGUOUS_CONTEXT
                        ? MEMORIA_CONCEPT_REWRITE_REASON_AMBIGUOUS_CONTEXT
                        : MEMORIA_CONCEPT_REWRITE_REASON_AMBIGUOUS;
                    snprintf(out.rewritten_query, sizeof(out.rewritten_query), "%s", query);
                    return out;
                }
            }
            if (r.status != MEMORIA_CONCEPT_HIT || !r.concept_id[0]) continue;
            concept = find_concept(index, r.concept_id, namespace_name);
            if (!concept) {
                out.status = MEMORIA_CONCEPT_REWRITE_UNRESOLVED;
                out.reason = MEMORIA_CONCEPT_REWRITE_REASON_MISSING_CONCEPT;
                snprintf(out.rewritten_query, sizeof(out.rewritten_query), "%s", query);
                return out;
            }
            if (!append_text(out.rewritten_query, sizeof(out.rewritten_query), &used, concept->canonical, used != 0) ||
                !remember_id(&out, concept->concept_id)) {
                out.status = MEMORIA_CONCEPT_REWRITE_UNRESOLVED;
                out.reason = MEMORIA_CONCEPT_REWRITE_REASON_CAPACITY;
                return out;
            }
            if (strcmp(concept->canonical, surface) != 0) changed = 1;
            i += width;
            matched = 1;
            break;
        }
        if (!matched) {
            if (!append_text(out.rewritten_query, sizeof(out.rewritten_query), &used, words[i], used != 0)) {
                out.status = MEMORIA_CONCEPT_REWRITE_UNRESOLVED;
                out.reason = MEMORIA_CONCEPT_REWRITE_REASON_CAPACITY;
                return out;
            }
            ++i;
        }
    }
    out.status = changed ? MEMORIA_CONCEPT_REWRITE_REWRITTEN : MEMORIA_CONCEPT_REWRITE_UNCHANGED;
    out.reason = MEMORIA_CONCEPT_REWRITE_REASON_NONE;
    return out;
}
