#include "retrieval_v2_semantic_adapter.h"
#include "retrieval_v2_normalization.h"

#include <ctype.h>
#include <math.h>
#include <stdlib.h>
#include <string.h>

#define RAW_TOKEN_CAP 96u
#define AMBIGUITY_TOKEN_CAP 64u
#define AMBIGUITY_MAX_TOKENS 64u

static int append_bytes(char **buffer, size_t *length, size_t *capacity, const char *text, size_t n) {
    char *next;
    size_t needed;
    if (!buffer || !length || !capacity || (!text && n)) return 0;
    needed = *length + n + 1u;
    if (needed > *capacity) {
        size_t next_capacity = *capacity ? *capacity : 128u;
        while (next_capacity < needed) {
            if (next_capacity > ((size_t)-1) / 2u) return 0;
            next_capacity *= 2u;
        }
        next = (char *)realloc(*buffer, next_capacity);
        if (!next) return 0;
        *buffer = next;
        *capacity = next_capacity;
    }
    if (n) memcpy(*buffer + *length, text, n);
    *length += n;
    (*buffer)[*length] = 0;
    return 1;
}

static int token_char(unsigned char ch) {
    return ch >= 0x80u || isalnum(ch);
}

static char *normalize_text_copy(const char *input) {
    char *out = NULL;
    size_t out_len = 0u, out_cap = 0u, i = 0u;
    int had_question = 0;
    if (!input) return NULL;

    while (input[i]) {
        char raw[RAW_TOKEN_CAP];
        char normalized[RAW_TOKEN_CAP];
        size_t k = 0u;
        unsigned char ch = (unsigned char)input[i];
        if (input[i] == '?') had_question = 1;
        if (!token_char(ch)) {
            ++i;
            continue;
        }
        while (input[i] && token_char((unsigned char)input[i])) {
            if (k + 1u >= sizeof(raw)) {
                free(out);
                return NULL;
            }
            raw[k++] = input[i++];
        }
        raw[k] = 0;
        if (!memoria_retrieval_v2_normalize_token(raw, normalized, sizeof(normalized))) continue;
        if (out_len && !append_bytes(&out, &out_len, &out_cap, " ", 1u)) {
            free(out);
            return NULL;
        }
        if (!append_bytes(&out, &out_len, &out_cap, normalized, strlen(normalized))) {
            free(out);
            return NULL;
        }
    }
    if (!out) {
        out = (char *)calloc(1u, 1u);
        if (!out) return NULL;
    }
    if (had_question && !append_bytes(&out, &out_len, &out_cap, "?", 1u)) {
        free(out);
        return NULL;
    }
    return out;
}

static int ambiguity_stopword(const char *w) {
    static const char *stop[] = {
        "a","as","da","das","de","do","dos","e","em","o","os","para","por","que","um","uma",
        "me","fale","sobre","qual","quais","what","which","the","of","is","tell","about"
    };
    size_t i;
    for (i = 0u; i < sizeof(stop)/sizeof(stop[0]); ++i)
        if (strcmp(w, stop[i]) == 0) return 1;
    return 0;
}

static size_t split_meaningful_tokens(const char *text, char out[][AMBIGUITY_TOKEN_CAP], size_t cap) {
    size_t count = 0u, i = 0u;
    if (!text) return 0u;
    while (text[i] && count < cap) {
        size_t k = 0u;
        while (text[i] == ' ') ++i;
        if (!text[i]) break;
        while (text[i] && text[i] != ' ') {
            if (k + 1u < AMBIGUITY_TOKEN_CAP && text[i] != '?') out[count][k++] = text[i];
            ++i;
        }
        out[count][k] = 0;
        if (k && !ambiguity_stopword(out[count])) ++count;
    }
    return count;
}

static int text_has_token(const char *text, const char *token) {
    size_t n;
    const char *p;
    if (!text || !token || !*token) return 0;
    n = strlen(token);
    p = text;
    while ((p = strstr(p, token)) != NULL) {
        int left_ok = (p == text || p[-1] == ' ');
        int right_ok = (p[n] == 0 || p[n] == ' ' || p[n] == '?');
        if (left_ok && right_ok) return 1;
        ++p;
    }
    return 0;
}

static size_t query_overlap(const char *normalized_query, const char *normalized_text) {
    char q[AMBIGUITY_MAX_TOKENS][AMBIGUITY_TOKEN_CAP];
    size_t nq = split_meaningful_tokens(normalized_query, q, AMBIGUITY_MAX_TOKENS);
    size_t i, hits = 0u;
    for (i = 0u; i < nq; ++i)
        if (text_has_token(normalized_text, q[i])) ++hits;
    return hits;
}

static const char *source_root(const memoria_semantic_source *s) {
    if (!s) return NULL;
    if (s->ultimate_source_memory_id && s->ultimate_source_memory_id[0]) return s->ultimate_source_memory_id;
    return s->memory_id;
}

static int normalized_ambiguity(
    const char *normalized_query,
    const memoria_semantic_source *sources,
    char **normalized_texts,
    size_t source_count
) {
    size_t i, best_overlap = 0u, best_index = 0u;
    int found = 0;
    for (i = 0u; i < source_count; ++i) {
        size_t overlap = query_overlap(normalized_query, normalized_texts[i]);
        if (!found || overlap > best_overlap) {
            best_overlap = overlap;
            best_index = i;
            found = 1;
        }
    }
    /* One shared concept is too weak for this pre-check because entity overview
     * ranking (e.g. China vs Air China) intentionally resolves such cases. */
    if (!found || best_overlap < 2u) return 0;
    for (i = 0u; i < source_count; ++i) {
        const char *a_root;
        const char *b_root;
        if (i == best_index || query_overlap(normalized_query, normalized_texts[i]) != best_overlap) continue;
        if (fabs(sources[i].authority - sources[best_index].authority) >= 0.05) continue;
        a_root = source_root(&sources[best_index]);
        b_root = source_root(&sources[i]);
        if (a_root && b_root && strcmp(a_root, b_root) == 0) continue;
        if (strcmp(normalized_texts[i], normalized_texts[best_index]) == 0) continue;
        return 1;
    }
    return 0;
}

memoria_semantic_result memoria_retrieval_v2_resolve_sources(
    const char *query,
    const memoria_semantic_source *sources,
    size_t source_count
) {
    memoria_semantic_result unresolved = {0, 0, 0.0, 0, 0.0, 0};
    memoria_semantic_source *normalized_sources = NULL;
    char **normalized_texts = NULL;
    char *normalized_query = NULL;
    memoria_semantic_result result;
    size_t i;

    if (!query || !sources || !source_count) return unresolved;
    normalized_query = normalize_text_copy(query);
    normalized_sources = (memoria_semantic_source *)calloc(source_count, sizeof(*normalized_sources));
    normalized_texts = (char **)calloc(source_count, sizeof(*normalized_texts));
    if (!normalized_query || !normalized_sources || !normalized_texts) goto fail;

    for (i = 0u; i < source_count; ++i) {
        normalized_sources[i] = sources[i];
        normalized_texts[i] = normalize_text_copy(sources[i].text);
        if (!normalized_texts[i]) goto fail;
        normalized_sources[i].text = normalized_texts[i];
    }

    if (normalized_ambiguity(normalized_query, sources, normalized_texts, source_count))
        result = unresolved;
    else
        result = memoria_semantic_resolve_sources(normalized_query, normalized_sources, source_count);

    for (i = 0u; i < source_count; ++i) free(normalized_texts[i]);
    free(normalized_texts);
    free(normalized_sources);
    free(normalized_query);
    return result;

fail:
    if (normalized_texts) for (i = 0u; i < source_count; ++i) free(normalized_texts[i]);
    free(normalized_texts);
    free(normalized_sources);
    free(normalized_query);
    return unresolved;
}
