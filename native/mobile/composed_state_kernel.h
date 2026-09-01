#ifndef MEMORIA_COMPOSED_STATE_KERNEL_H
#define MEMORIA_COMPOSED_STATE_KERNEL_H

#include <stddef.h>

#include "temporal_state_kernel.h"

#define MEMORIA_COMPOSED_STATE_MAX_ITEMS 8u

typedef struct memoria_composed_state_item {
    const char *property;
    const char *value;
    const char *memory_id;
    long order;
    double authority;
} memoria_composed_state_item;

typedef struct memoria_composed_state_result {
    int hit;
    const char *entity;
    memoria_composed_state_item items[MEMORIA_COMPOSED_STATE_MAX_ITEMS];
    size_t item_count;
    double confidence;
    int ambiguous;
} memoria_composed_state_result;

/*
 * Resolve a read-only current state composed from already-materialized facts.
 *
 * No new fact or relation is inferred. Every returned value remains attached
 * to the exact memory that supplied it. All requested properties must resolve
 * uniquely; a conflicting tie at the latest order makes the whole composition
 * unresolved rather than selecting arbitrarily.
 */
memoria_composed_state_result memoria_composed_state_resolve(
    const char *entity,
    const char *const *properties,
    size_t property_count,
    const memoria_state_fact *facts,
    size_t fact_count
);

#endif
