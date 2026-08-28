#include "semantic_kernel.h"

#include <ctype.h>
#include <math.h>
#include <stddef.h>
#include <string.h>

#define MAX_TOKENS 96
#define MAX_TOKEN_BYTES 64

typedef struct token_set {
    char tokens[MAX_TOKENS][MAX_TOKEN_BYTES];
    size_t count;
} token_set;

static int is_word_byte(unsigned char ch) {
    return isalnum(ch) || ch == '_' || ch == '-' || ch >= 0x80;
}

static void token_set_add(token_set *set, const char *token) {
    size_t i;
    if (!token || !*token || set->count >= MAX_TOKENS) return;
    for (i = 0; i < set->count; ++i) {
        if (strcmp(set->tokens[i], token) == 0) return;
    }
    strncpy(set->tokens[set->count], token, MAX_TOKEN_BYTES - 1);
    set->tokens[set->count][MAX_TOKEN_BYTES - 1] = '\0';
    set->count += 1;
}

static token_set tokenize(const char *text) {
    token_set set = {{{0}}, 0};
    char current[MAX_TOKEN_BYTES] = {0};
    size_t used = 0;
    const unsigned char *p = (const unsigned char *)text;
    if (!text) return set;
    while (*p) {
        if (is_word_byte(*p)) {
            if (used + 1 < sizeof(current)) {
                current[used++] = (*p < 0x80) ? (char)tolower(*p) : (char)*p;
            }
        } else if (used) {
            current[used] = '\0';
            token_set_add(&set, current);
            used = 0;
        }
        ++p;
    }
    if (used) {
        current[used] = '\0';
        token_set_add(&set, current);
    }
    return set;
}

static size_t overlap_count(const token_set *a, const token_set *b) {
    size_t i, j, count = 0;
    for (i = 0; i < a->count; ++i) {
        for (j = 0; j < b->count; ++j) {
            if (strcmp(a->tokens[i], b->tokens[j]) == 0) {
                count += 1;
                break;
            }
        }
    }
    return count;
}

static int same_text(const char *a, const char *b) {
    if (!a || !b) return a == b;
    return strcmp(a, b) == 0;
}

static int same_root(const memoria_kernel_candidate *a, const memoria_kernel_candidate *b) {
    const char *ar = a->root_memory_id ? a->root_memory_id : a->memory_id;
    const char *br = b->root_memory_id ? b->root_memory_id : b->memory_id;
    return ar && br && strcmp(ar, br) == 0;
}

memoria_kernel_result memoria_kernel_resolve(
    const char *query,
    const memoria_kernel_candidate *candidates,
    size_t candidate_count
) {
    memoria_kernel_result unresolved = {MEMORIA_KERNEL_UNRESOLVED, 0, 0.0};
    token_set query_tokens;
    double scores[256];
    double best = 0.0;
    size_t i, j;
    size_t best_index = 0;
    double best_authority = -1.0;
    int best_order = -1;

    if (!query || !*query || !candidates || candidate_count == 0 || candidate_count > 256) return unresolved;
    query_tokens = tokenize(query);
    if (query_tokens.count == 0) return unresolved;

    for (i = 0; i < candidate_count; ++i) {
        token_set context_tokens = tokenize(candidates[i].context);
        size_t overlap = overlap_count(&query_tokens, &context_tokens);
        scores[i] = (double)overlap / (double)query_tokens.count;
        if (scores[i] > best) best = scores[i];
    }
    if (best <= 0.0) return unresolved;

    /* Exact semantic ties from independent roots with different contexts abstain. */
    for (i = 0; i < candidate_count; ++i) {
        if (fabs(scores[i] - best) > 1e-12) continue;
        for (j = i + 1; j < candidate_count; ++j) {
            if (fabs(scores[j] - best) > 1e-12) continue;
            if (!same_root(&candidates[i], &candidates[j]) &&
                !same_text(candidates[i].context, candidates[j].context)) {
                return unresolved;
            }
        }
    }

    /* Authority is evaluated only inside the near-best relevance pool. */
    for (i = 0; i < candidate_count; ++i) {
        const char *root;
        int explicit_root;
        if (scores[i] < best - 0.15) continue;
        root = candidates[i].root_memory_id ? candidates[i].root_memory_id : candidates[i].memory_id;
        explicit_root = root && candidates[i].memory_id && strcmp(root, candidates[i].memory_id) == 0;

        if (candidates[i].source_authority > best_authority ||
            (fabs(candidates[i].source_authority - best_authority) < 1e-12 && explicit_root &&
             !(candidates[best_index].root_memory_id && candidates[best_index].memory_id &&
               strcmp(candidates[best_index].root_memory_id, candidates[best_index].memory_id) == 0)) ||
            (fabs(candidates[i].source_authority - best_authority) < 1e-12 &&
             candidates[i].created_order > best_order)) {
            best_index = i;
            best_authority = candidates[i].source_authority;
            best_order = candidates[i].created_order;
        }
    }

    {
        memoria_kernel_result hit = {MEMORIA_KERNEL_HIT, best_index, scores[best_index]};
        return hit;
    }
}
