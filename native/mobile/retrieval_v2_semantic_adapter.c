#include "retrieval_v2_semantic_adapter.h"
#include "retrieval_v2_normalization.h"

#include <ctype.h>
#include <stdlib.h>
#include <string.h>

#define RAW_TOKEN_CAP 96u

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
