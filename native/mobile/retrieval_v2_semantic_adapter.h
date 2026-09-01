#ifndef MEMORIA_RETRIEVAL_V2_SEMANTIC_ADAPTER_H
#define MEMORIA_RETRIEVAL_V2_SEMANTIC_ADAPTER_H

#include "semantic_kernel.h"

#include <stddef.h>

/* Experimental Retrieval v2 adapter.
 * Normalizes query/source lexical forms on transient copies and delegates to
 * the existing semantic kernel. Persistent memory is never rewritten here.
 */
memoria_semantic_result memoria_retrieval_v2_resolve_sources(
    const char *query,
    const memoria_semantic_source *sources,
    size_t source_count
);

#endif
