#ifndef MEMORIA_SEMANTIC_CONSOLIDATION_STATE_H
#define MEMORIA_SEMANTIC_CONSOLIDATION_STATE_H

#include "mobile_persistence.h"
#include "semantic_consolidation_kernel.h"

#include <stddef.h>

/*
 * Build conservative semantic consolidation candidates from persisted/native
 * turn rows. Only direct factual evidence contributes support. Generated,
 * replayed and already-derived memories never become independent evidence.
 * Existing active derived memories suppress duplicate candidates for the same
 * exact normalized claim.
 */
size_t memoria_semantic_consolidation_from_turns(
    const memoria_persist_turn *turns,
    size_t turn_count,
    size_t min_independent_roots,
    memoria_semantic_candidate *out,
    size_t out_capacity
);

#endif
