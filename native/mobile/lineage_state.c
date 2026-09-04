#include "lineage_state.h"
#include "lineage_adapter.h"

#include <stdlib.h>

int memoria_lineage_rows_resolve(
    const memoria_persist_turn *turns,
    size_t turn_count,
    const char *memory_id,
    const char *namespace_id,
    memoria_lineage_result *out
) {
    memoria_lineage_graph graph = {0};
    memoria_lineage_result result = {0};
    int ok = 0;

    if (!memory_id || !*memory_id || !out || (turn_count && !turns)) return 0;
    *out = result;
    if (!turn_count) return 1;

    if (!memoria_lineage_graph_build(turns, turn_count, &graph))
        return 0;

    result = memoria_lineage_graph_resolve(&graph, memory_id, namespace_id);
    *out = result;
    ok = 1;
    memoria_lineage_graph_free(&graph);
    return ok;
}

int memoria_lineage_state_resolve(
    memoria_persistence *persistence,
    const char *memory_id,
    const char *namespace_id,
    memoria_lineage_result *out
) {
    memoria_persist_turn *turns = NULL;
    memoria_lineage_result result = {0};
    size_t turn_count = 0, episode_count = 0, i;
    unsigned long sequence = 0;
    int ok = 0;

    if (!persistence || !memory_id || !*memory_id || !out) return 0;
    *out = result;

    if (!memoria_persistence_meta(
            persistence,
            &turn_count,
            &episode_count,
            &sequence)) return 0;
    (void)episode_count;
    (void)sequence;

    if (!turn_count) return 1;
    if (turn_count > ((size_t)-1) / sizeof(*turns)) return 0;

    turns = (memoria_persist_turn *)calloc(turn_count, sizeof(*turns));
    if (!turns) return 0;

    for (i = 0; i < turn_count; ++i) {
        if (!memoria_persistence_load_turn(persistence, i + 1u, &turns[i]))
            goto cleanup;
    }

    ok = memoria_lineage_rows_resolve(turns, turn_count, memory_id, namespace_id, out);

cleanup:
    if (turns) {
        for (i = 0; i < turn_count; ++i)
            memoria_persistence_free_turn(&turns[i]);
        free(turns);
    }
    return ok;
}
