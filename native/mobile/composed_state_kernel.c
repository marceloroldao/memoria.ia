#include "composed_state_kernel.h"

#include <ctype.h>
#include <math.h>
#include <string.h>

static int eq_ci(const char *a, const char *b) {
    if (!a || !b) return 0;
    while (*a && *b) {
        if (tolower((unsigned char)*a) != tolower((unsigned char)*b)) return 0;
        ++a; ++b;
    }
    return *a == 0 && *b == 0;
}

static int latest_unique_fact(
    const char *entity,
    const char *property,
    const memoria_state_fact *facts,
    size_t fact_count,
    const memoria_state_fact **out
) {
    const memoria_state_fact *best = NULL;
    size_t i;
    int ambiguous = 0;

    if (!entity || !*entity || !property || !*property || !facts || !out) return 0;

    for (i = 0; i < fact_count; ++i) {
        const memoria_state_fact *f = &facts[i];
        if (!f->memory_id || !f->entity || !f->property || !f->value) continue;
        if (!eq_ci(entity, f->entity) || !eq_ci(property, f->property)) continue;

        if (!best || f->order > best->order) {
            best = f;
            ambiguous = 0;
        } else if (f->order == best->order) {
            if (!eq_ci(f->value, best->value)) {
                ambiguous = 1;
            } else if (f->authority > best->authority + 1e-12) {
                best = f;
            }
        }
    }

    if (!best || ambiguous) return 0;
    *out = best;
    return 1;
}

memoria_composed_state_result memoria_composed_state_resolve(
    const char *entity,
    const char *const *properties,
    size_t property_count,
    const memoria_state_fact *facts,
    size_t fact_count
) {
    memoria_composed_state_result none = {0};
    memoria_composed_state_result result = {0};
    size_t i, j;
    double confidence = 1.0;

    if (!entity || !*entity || !properties || property_count == 0u ||
        property_count > MEMORIA_COMPOSED_STATE_MAX_ITEMS || !facts || fact_count == 0u)
        return none;

    result.entity = entity;

    for (i = 0; i < property_count; ++i) {
        const memoria_state_fact *current = NULL;
        const char *property = properties[i];

        if (!property || !*property) return none;
        for (j = 0; j < i; ++j) if (eq_ci(property, properties[j])) return none;

        if (!latest_unique_fact(entity, property, facts, fact_count, &current)) {
            result.ambiguous = 1;
            return result;
        }

        result.items[i].property = property;
        result.items[i].value = current->value;
        result.items[i].memory_id = current->memory_id;
        result.items[i].order = current->order;
        result.items[i].authority = current->authority;
        if (current->authority < confidence) confidence = current->authority;
    }

    if (confidence < 0.0) confidence = 0.0;
    if (confidence > 1.0) confidence = 1.0;
    result.hit = 1;
    result.item_count = property_count;
    result.confidence = confidence;
    result.ambiguous = 0;
    return result;
}
