#ifndef MEMORIA_TEMPORAL_STATE_KERNEL_H
#define MEMORIA_TEMPORAL_STATE_KERNEL_H

#include <stddef.h>

typedef struct memoria_state_fact {
    const char *memory_id;
    const char *entity;
    const char *property;
    const char *value;
    long order;
    double authority;
} memoria_state_fact;

typedef struct memoria_temporal_state_result {
    int hit;
    const char *previous_memory_id;
    const char *current_memory_id;
    const char *previous_value;
    const char *current_value;
    long previous_order;
    long current_order;
    double confidence;
    int transition_detected;
} memoria_temporal_state_result;

memoria_temporal_state_result memoria_temporal_state_resolve(
    const char *entity,
    const char *property,
    const memoria_state_fact *facts,
    size_t fact_count
);

#endif
