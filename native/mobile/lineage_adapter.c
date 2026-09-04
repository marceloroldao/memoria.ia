#include "lineage_adapter.h"

#include <stdlib.h>
#include <string.h>

static size_t required_nodes(const memoria_persist_turn *turns, size_t turn_count) {
    size_t total = turn_count;
    size_t i;
    for (i = 0; i < turn_count; ++i) total += turns[i].relation_count;
    return total;
}

int memoria_lineage_graph_build(
    const memoria_persist_turn *turns,
    size_t turn_count,
    memoria_lineage_graph *out
) {
    memoria_lineage_node *nodes;
    size_t total, cursor = 0, i, j;
    if (!out) return 0;
    out->nodes = NULL;
    out->node_count = 0;
    if (!turns && turn_count) return 0;
    if (!turn_count) return 1;

    total = required_nodes(turns, turn_count);
    if (total < turn_count || total > ((size_t)-1) / sizeof(*nodes)) return 0;
    nodes = (memoria_lineage_node *)calloc(total, sizeof(*nodes));
    if (!nodes) return 0;

    for (i = 0; i < turn_count; ++i) {
        const memoria_persist_turn *turn = &turns[i];
        memoria_lineage_node *node = &nodes[cursor++];
        node->memory_id = turn->memory_id;
        node->namespace_id = turn->namespace_id;
        node->source_type = turn->source_type;
        node->ultimate_source_memory_id = turn->ultimate_source_memory_id;
        node->authority = turn->authority;
        node->order = turn->order;
        node->superseded = turn->superseded || turn->superseded_by[0];
        node->parent_count = turn->parent_count > MEMORIA_LINEAGE_MAX_PARENTS
            ? MEMORIA_LINEAGE_MAX_PARENTS : turn->parent_count;
        for (j = 0; j < node->parent_count; ++j)
            node->parent_memory_ids[j] = turn->parent_memory_ids[j];

        for (j = 0; j < turn->relation_count; ++j) {
            memoria_lineage_node *relation_node = &nodes[cursor++];
            relation_node->memory_id = turn->relation_memory_ids[j][0]
                ? turn->relation_memory_ids[j] : NULL;
            relation_node->namespace_id = turn->namespace_id;
            relation_node->source_type = "derived_relation";
            relation_node->ultimate_source_memory_id = turn->ultimate_source_memory_id;
            relation_node->authority = turn->relations[j].confidence;
            relation_node->order = turn->order;
            relation_node->superseded = node->superseded;
            relation_node->parent_memory_ids[0] = turn->memory_id;
            relation_node->parent_count = 1;
        }
    }

    out->nodes = nodes;
    out->node_count = cursor;
    return 1;
}

void memoria_lineage_graph_free(memoria_lineage_graph *graph) {
    if (!graph) return;
    free(graph->nodes);
    graph->nodes = NULL;
    graph->node_count = 0;
}

memoria_lineage_result memoria_lineage_graph_resolve(
    const memoria_lineage_graph *graph,
    const char *memory_id,
    const char *namespace_id
) {
    memoria_lineage_result inactive = {0};
    if (!graph || !graph->nodes || !graph->node_count) return inactive;
    return memoria_lineage_resolve(
        graph->nodes,
        graph->node_count,
        memory_id,
        namespace_id
    );
}
