#ifndef MEMORIA_LINEAGE_STATE_H
#define MEMORIA_LINEAGE_STATE_H

#include "lineage_kernel.h"
#include "mobile_persistence.h"

#include <stddef.h>

int memoria_lineage_rows_resolve(
    const memoria_persist_turn *turns,
    size_t turn_count,
    const char *memory_id,
    const char *namespace_id,
    memoria_lineage_result *out
);

int memoria_lineage_state_resolve(
    memoria_persistence *persistence,
    const char *memory_id,
    const char *namespace_id,
    memoria_lineage_result *out
);

#endif
