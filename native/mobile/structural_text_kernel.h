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
 * supplies one token, not a sentence. ASCII and Latin-1 uppercase letters are
 * case-folded compatibly with Python for the OFF.IA Portuguese text contract.
 * UTF-8 outside that parity subset is preserved by the symbol function.
 */
int memoria_structural_text_symbol(
    const char *token,
    size_t token_len,
    uint64_t *out_symbol
);

/*
 * Sentence -> opaque symbols for the first native OFF.IA text contract.
 *
 * Token membership matches the Python adapter for ASCII word characters plus
 * the explicit U+00C0..U+00FF Latin-1 range used by textual.py. Other Unicode
 * code points are treated as separators in this v1 tokenizer rather than being
 * assigned invented semantics. Passing out_symbols=NULL performs a count-only
 * pass and writes the required token count to out_count.
 */
int memoria_structural_text_tokenize(
    const char *text,
    size_t text_len,
    uint64_t *out_symbols,
    size_t out_capacity,
    size_t *out_count
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
