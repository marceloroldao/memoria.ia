#include "relation_extractor.h"
#include "relation_semantic_validator.h"

#include <string.h>

size_t memoria_extract_promotable_relations(const char *text, memoria_relation *out, size_t capacity) {
    memoria_relation raw[32];
    size_t raw_capacity, raw_count;

    if (!text || !out || capacity == 0u) return 0u;
    raw_capacity = capacity < (sizeof(raw) / sizeof(raw[0])) ? capacity : (sizeof(raw) / sizeof(raw[0]));
    memset(raw, 0, sizeof(raw));
    raw_count = memoria_extract_relations(text, raw, raw_capacity);
    return memoria_relation_filter_promotable(raw, raw_count, out, capacity);
}
