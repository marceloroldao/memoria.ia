#include "relation_extractor.h"
#include "relation_semantic_validator.h"
#include "typed_relation_extractor.h"

#include <string.h>

/* Provenance policy is scoped to the current ingesting thread. This keeps the
 * frozen v1 extractor ABI unchanged while allowing the post-v1 composition
 * layer to distinguish semantic validity from evidential eligibility. */
static _Thread_local int g_block_automatic_promotion = 0;

void memoria_relation_promotion_set_source_type(const char *source_type) {
    g_block_automatic_promotion = source_type && strcmp(source_type, "assistant_generated") == 0;
}

void memoria_relation_promotion_clear_source_type(void) {
    g_block_automatic_promotion = 0;
}

static int same_relation(const memoria_relation *a, const memoria_relation *b) {
    return strcmp(a->subject, b->subject) == 0 &&
           strcmp(a->predicate, b->predicate) == 0 &&
           strcmp(a->object, b->object) == 0;
}

static void append_unique(memoria_relation *rows, size_t *count, size_t capacity, const memoria_relation *candidate) {
    size_t i;
    for (i = 0; i < *count; ++i) if (same_relation(&rows[i], candidate)) return;
    if (*count < capacity) rows[(*count)++] = *candidate;
}

size_t memoria_extract_promotable_relations(const char *text, memoria_relation *out, size_t capacity) {
    memoria_relation raw[32], typed[16], combined[48];
    size_t raw_count, typed_count, combined_count = 0u, i;

    if (!text || !out || capacity == 0u || g_block_automatic_promotion) return 0u;
    memset(raw, 0, sizeof(raw));
    memset(typed, 0, sizeof(typed));
    memset(combined, 0, sizeof(combined));

    raw_count = memoria_extract_relations(text, raw, sizeof(raw) / sizeof(raw[0]));
    typed_count = memoria_extract_typed_relations(text, typed, sizeof(typed) / sizeof(typed[0]));

    for (i = 0; i < raw_count; ++i) append_unique(combined, &combined_count, sizeof(combined) / sizeof(combined[0]), &raw[i]);
    for (i = 0; i < typed_count; ++i) append_unique(combined, &combined_count, sizeof(combined) / sizeof(combined[0]), &typed[i]);

    return memoria_relation_filter_promotable(combined, combined_count, out, capacity);
}

/* The typed extractor is compiled into the post-v1 promotion unit so the frozen
 * CMake source list remains unchanged for this stabilization slice. */
#include "typed_relation_extractor.c"
