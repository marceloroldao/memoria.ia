#include "relation_extractor.h"
#include "relation_semantic_validator.h"

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

size_t memoria_extract_promotable_relations(const char *text, memoria_relation *out, size_t capacity) {
    memoria_relation raw[32];
    size_t raw_capacity, raw_count;

    if (!text || !out || capacity == 0u || g_block_automatic_promotion) return 0u;
    raw_capacity = capacity < (sizeof(raw) / sizeof(raw[0])) ? capacity : (sizeof(raw) / sizeof(raw[0]));
    memset(raw, 0, sizeof(raw));
    raw_count = memoria_extract_relations(text, raw, raw_capacity);
    return memoria_relation_filter_promotable(raw, raw_count, out, capacity);
}
