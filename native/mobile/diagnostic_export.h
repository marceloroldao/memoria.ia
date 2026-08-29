#ifndef MEMORIA_DIAGNOSTIC_EXPORT_H
#define MEMORIA_DIAGNOSTIC_EXPORT_H

#include "mobile_persistence.h"

#include <stddef.h>

typedef struct memoria_diagnostic_page {
    size_t turn_offset;
    size_t turn_limit;
    size_t episode_offset;
    size_t episode_limit;
} memoria_diagnostic_page;

/*
 * Builds a versioned, read-only UTF-8 JSON diagnostic snapshot from already
 * materialized mobile state. The caller owns the returned malloc() buffer.
 * Pagination bounds snapshot memory use without exposing BDR internals.
 */
char *memoria_diagnostic_export_json(
    const char *organization_id,
    unsigned long sequence,
    const memoria_persist_turn *turns,
    size_t turn_count,
    const memoria_persist_episode *episodes,
    size_t episode_count,
    memoria_diagnostic_page page
);

#endif
