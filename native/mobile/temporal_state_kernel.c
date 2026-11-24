#include "temporal_state_kernel.h"

#include <ctype.h>
#include <string.h>

static int eq_ci(const char *a, const char *b) {
    if (!a || !b) return 0;
    while (*a && *b) {
        if (tolower((unsigned char)*a) != tolower((unsigned char)*b)) return 0;
        ++a; ++b;
    }
    return *a == 0 && *b == 0;
}

static int matches_property(const memoria_state_fact *fact, const char *entity, const char *property) {
    return fact->memory_id && fact->value && eq_ci(entity, fact->entity) && eq_ci(property, fact->property);
}

memoria_temporal_state_result memoria_temporal_state_resolve(
    const char *entity,
    const char *property,
    const memoria_state_fact *facts,
    size_t fact_count
) {
    memoria_temporal_state_result none = {0,0,0,0,0,0,0,0.0,0};
    size_t i;
    const memoria_state_fact *latest = 0;
    const memoria_state_fact *previous = 0;

    if (!entity || !*entity || !property || !*property || !facts || !fact_count) return none;

    for (i = 0; i < fact_count; ++i) {
        const memoria_state_fact *fact = &facts[i];
        if (matches_property(fact, entity, property) && (!latest || fact->order > latest->order))
            latest = fact;
    }
    if (!latest) return none;

    /* Repeated observations of the current value do not mark a transition. */
    for (i = 0; i < fact_count; ++i) {
        const memoria_state_fact *fact = &facts[i];
        if (matches_property(fact, entity, property) &&
            fact->order < latest->order && !eq_ci(fact->value, latest->value) &&
            (!previous || fact->order > previous->order))
            previous = fact;
    }

    /* Check all values at both boundaries, including repeats skipped above. */
    for (i = 0; i < fact_count; ++i) {
        const memoria_state_fact *fact = &facts[i];
        if (!matches_property(fact, entity, property)) continue;
        if (fact->order == latest->order && !eq_ci(fact->value, latest->value)) return none;
        if (previous && fact->order == previous->order && !eq_ci(fact->value, previous->value))
            previous = NULL;
    }

    {
        memoria_temporal_state_result r;
        r.hit = 1;
        r.previous_memory_id = previous ? previous->memory_id : 0;
        r.current_memory_id = latest->memory_id;
        r.previous_value = previous ? previous->value : 0;
        r.current_value = latest->value;
        r.previous_order = previous ? previous->order : 0;
        r.current_order = latest->order;
        r.transition_detected = previous != NULL;
        r.confidence = latest->authority;
        if (previous && previous->authority < r.confidence) r.confidence = previous->authority;
        if (r.confidence < 0.0) r.confidence = 0.0;
        if (r.confidence > 1.0) r.confidence = 1.0;
        return r;
    }
}
