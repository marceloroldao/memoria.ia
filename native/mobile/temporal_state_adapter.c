#include "temporal_state_adapter.h"

#include <string.h>

size_t memoria_temporal_build_facts(
    const memoria_temporal_relation_source *sources,
    size_t source_count,
    memoria_state_fact *out,
    size_t capacity
) {
    size_t i, j, count = 0;
    if (!sources || !out || capacity == 0) return 0;

    for (i = 0; i < source_count && count < capacity; ++i) {
        const memoria_temporal_relation_source *s = &sources[i];
        if (!s->memory_id || !s->relations) continue;
        for (j = 0; j < s->relation_count && count < capacity; ++j) {
            const memoria_relation *r = &s->relations[j];
            if (!r->subject[0] || !r->predicate[0] || !r->object[0]) continue;
            out[count].memory_id = s->memory_id;
            out[count].entity = r->subject;
            out[count].property = r->predicate;
            out[count].value = r->object;
            out[count].order = s->order;
            out[count].authority = s->authority;
            ++count;
        }
    }
    return count;
}
