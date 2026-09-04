#ifndef MEMORIA_LINEAGE_STATE_H
#define MEMORIA_LINEAGE_STATE_H

#include "lineage_kernel.h"
#include "mobile_persistence.h"

int memoria_lineage_state_resolve(
    memoria_persistence *persistence,
    const char *memory_id,
    const char *namespace_id,
    memoria_lineage_result *out
);

#endif
