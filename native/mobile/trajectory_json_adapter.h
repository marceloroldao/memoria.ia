#ifndef MEMORIA_TRAJECTORY_JSON_ADAPTER_H
#define MEMORIA_TRAJECTORY_JSON_ADAPTER_H

#include <stddef.h>
#include "trajectory_kernel.h"

int memoria_trajectory_resolve_json(
    const char *request_json,
    const char *query,
    const memoria_semantic_source *sources,
    size_t source_count,
    memoria_trajectory_result *out_result,
    size_t *out_window_count
);

#endif
