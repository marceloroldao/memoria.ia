#ifndef MEMORIA_TRAJECTORY_JSON_ADAPTER_H
#define MEMORIA_TRAJECTORY_JSON_ADAPTER_H

#include <stddef.h>
#include "trajectory_kernel.h"

/*
 * Parse the optional trajectory fields from resolve_context JSON and run the
 * trajectory kernel. Return values:
 *   1  conversation_window was present and out_result is valid
 *   0  no conversation_window was present (caller should use classic resolver)
 *  -1  malformed/unsupported trajectory payload
 *
 * Accepted additive payload shape:
 * {
 *   "query":"...",
 *   "session_id":"session-1",
 *   "conversation_window":[
 *     {"session_id":"session-1","role":"user","text":"...","order":1}
 *   ]
 * }
 */
int memoria_trajectory_resolve_json(
    const char *request_json,
    const char *query,
    const memoria_semantic_source *sources,
    size_t source_count,
    memoria_trajectory_result *out_result,
    size_t *out_window_count
);

#endif
