#ifndef MEMORIA_STRUCTURAL_TEXT_KERNEL_H
#define MEMORIA_STRUCTURAL_TEXT_KERNEL_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define MEMORIA_STRUCTURAL_CHANNEL_ANY 0
#define MEMORIA_STRUCTURAL_CHANNEL_WITHIN 1
#define MEMORIA_STRUCTURAL_CHANNEL_TEMPORAL 2

typedef struct memoria_structural_text_field memoria_structural_text_field;

typedef struct memoria_structural_text_score {
    double score;
    size_t exact_overlap;
    double association_mass;
} memoria_structural_text_score;

/*
 * Deterministic token -> opaque 64-bit symbol.
 *
 * This is the native counterpart of Python structural_text_symbol(). The caller
 * supplies one token, not a sentence. ASCII letters are case-folded to lower
 * case before hashing. Non-ASCII UTF-8 bytes are preserved; full Unicode
 * tokenization/case-folding is intentionally outside this first parity kernel.
 */
int memoria_structural_text_symbol(
    const char *token,
    size_t token_len,
    uint64_t *out_symbol
);

memoria_structural_text_field *memoria_structural_text_field_create(
    size_t max_within_distance,
    size_t max_event_lag,
    double forgetting_rate
);

void memoria_structural_text_field_destroy(memoria_structural_text_field *field);

int memoria_structural_text_field_observe(
    memoria_structural_text_field *field,
    const uint64_t *trail,
    size_t trail_count
);

double memoria_structural_text_field_association(
    const memoria_structural_text_field *field,
    uint64_t source,
    uint64_t target,
    int channel
);

size_t memoria_structural_text_field_edge_count(
    const memoria_structural_text_field *field
);

uint64_t memoria_structural_text_field_tick(
    const memoria_structural_text_field *field
);

int memoria_structural_text_score_candidate(
    const memoria_structural_text_field *field,
    const uint64_t *query,
    size_t query_count,
    const uint64_t *candidate,
    size_t candidate_count,
    memoria_structural_text_score *out_score
);

#ifdef __cplusplus
}
#endif

#endif
