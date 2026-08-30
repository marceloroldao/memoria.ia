#ifndef MEMORIA_TRAJECTORY_KERNEL_H
#define MEMORIA_TRAJECTORY_KERNEL_H

#include <stddef.h>
#include "semantic_kernel.h"

#define MEMORIA_TRAJECTORY_MAX_SELECTED 2

typedef struct memoria_trajectory_turn {
    const char *session_id;
    const char *role;
    const char *text;
    long order;
} memoria_trajectory_turn;

typedef struct memoria_trajectory_result {
    int hit;
    const char *memory_id;
    double confidence;
    int used_window;
    size_t memory_count;
    const char *memory_ids[MEMORIA_TRAJECTORY_MAX_SELECTED];
} memoria_trajectory_result;

memoria_trajectory_result memoria_trajectory_resolve(
    const char *query,
    const char *session_id,
    const memoria_trajectory_turn *window,
    size_t window_count,
    const memoria_semantic_source *sources,
    size_t source_count
);

#endif
