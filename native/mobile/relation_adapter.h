#ifndef MEMORIA_RELATION_ADAPTER_H
#define MEMORIA_RELATION_ADAPTER_H

#include <stddef.h>

#include "relation_extractor.h"

/* Formats extracted relations as a Product-contract-compatible JSON array.
 * Returns 1 on success, 0 when the output buffer is insufficient/invalid.
 * Domain semantics remain entirely in the generic extractor.
 */
int memoria_relations_to_json(
    const memoria_relation *relations,
    size_t relation_count,
    const char *source_memory_id,
    char *out,
    size_t out_size
);

#endif
