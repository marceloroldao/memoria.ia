#ifndef MEMORIA_LINEAGE_ADAPTER_H
#define MEMORIA_LINEAGE_ADAPTER_H

#include "lineage_kernel.h"
#include "mobile_persistence.h"

#include <stddef.h>

typedef struct memoria_lineage_graph {
    memoria_lineage_node *nodes;
    size_t node_count;
} memoria_lineage_graph;

int memoria_lineage_graph_build(
    const memoria_persist_turn *turns,
    size_t turn_count,
    memoria_lineage_graph *out
);

void memoria_lineage_graph_free(memoria_lineage_graph *graph);

memoria_lineage_result memoria_lineage_graph_resolve(
    const memoria_lineage_graph *graph,
    const char *memory_id,
    const char *namespace_id
);

#endif
