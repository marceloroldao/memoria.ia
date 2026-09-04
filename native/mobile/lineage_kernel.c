#include "lineage_kernel.h"

#include <string.h>

#define MEMORIA_LINEAGE_MAX_VISITED 128u

typedef struct resolve_ctx {
    const memoria_lineage_node *nodes;
    size_t node_count;
    const char *namespace_id;
    const char *visited[MEMORIA_LINEAGE_MAX_VISITED];
    size_t visited_count;
} resolve_ctx;

static int same_namespace(const char *a, const char *b) {
    const char *left = a ? a : "";
    const char *right = b ? b : "";
    return strcmp(left, right) == 0;
}

int memoria_lineage_is_factual_root_type(const char *source_type) {
    return source_type && (
        strcmp(source_type, "user_assertion") == 0 ||
        strcmp(source_type, "user_correction") == 0 ||
        strcmp(source_type, "external_public") == 0 ||
        strcmp(source_type, "external_private") == 0 ||
        strcmp(source_type, "sensor_observation") == 0
    );
}

int memoria_lineage_is_conjunctive_type(const char *source_type) {
    return source_type && strcmp(source_type, "derived_relation") == 0;
}

static const memoria_lineage_node *find_node(
    const resolve_ctx *ctx,
    const char *memory_id
) {
    size_t i;
    if (!ctx || !memory_id || !*memory_id) return NULL;
    for (i = 0; i < ctx->node_count; ++i) {
        const memoria_lineage_node *node = &ctx->nodes[i];
        if (!node->memory_id || strcmp(node->memory_id, memory_id) != 0) continue;
        if (!same_namespace(node->namespace_id, ctx->namespace_id)) continue;
        return node;
    }
    return NULL;
}

static int already_visited(const resolve_ctx *ctx, const char *memory_id) {
    size_t i;
    for (i = 0; i < ctx->visited_count; ++i)
        if (strcmp(ctx->visited[i], memory_id) == 0) return 1;
    return 0;
}

static memoria_lineage_result inactive_result(void) {
    memoria_lineage_result result = {0};
    return result;
}

static memoria_lineage_result resolve_node(resolve_ctx *ctx, const char *memory_id) {
    const memoria_lineage_node *node;
    memoria_lineage_result result = {0};
    size_t i;

    if (!ctx || !memory_id || !*memory_id) return result;
    if (already_visited(ctx, memory_id)) return result;
    if (ctx->visited_count >= MEMORIA_LINEAGE_MAX_VISITED) return result;
    ctx->visited[ctx->visited_count++] = memory_id;

    node = find_node(ctx, memory_id);
    if (!node || node->superseded) {
        --ctx->visited_count;
        return result;
    }

    if (memoria_lineage_is_factual_root_type(node->source_type)) {
        result.factual_active = 1;
        result.representative_root_id = node->memory_id;
        --ctx->visited_count;
        return result;
    }

    if (memoria_lineage_is_conjunctive_type(node->source_type) && node->parent_count) {
        const char *representative = NULL;
        result.required_parent_count = node->parent_count;
        for (i = 0; i < node->parent_count; ++i) {
            memoria_lineage_result parent;
            if (!node->parent_memory_ids[i] || !*node->parent_memory_ids[i]) {
                --ctx->visited_count;
                return inactive_result();
            }
            parent = resolve_node(ctx, node->parent_memory_ids[i]);
            if (!parent.factual_active) {
                --ctx->visited_count;
                return inactive_result();
            }
            ++result.active_parent_count;
            if (!representative || strcmp(parent.representative_root_id, representative) < 0)
                representative = parent.representative_root_id;
        }
        result.factual_active = result.active_parent_count == result.required_parent_count;
        result.representative_root_id = result.factual_active ? representative : NULL;
        --ctx->visited_count;
        return result;
    }

    if (node->parent_count) {
        memoria_lineage_result best = {0};
        for (i = 0; i < node->parent_count; ++i) {
            memoria_lineage_result parent = resolve_node(ctx, node->parent_memory_ids[i]);
            if (!parent.factual_active) continue;
            if (!best.factual_active || strcmp(parent.representative_root_id, best.representative_root_id) < 0)
                best = parent;
        }
        --ctx->visited_count;
        return best;
    }

    if (node->ultimate_source_memory_id && *node->ultimate_source_memory_id &&
        strcmp(node->ultimate_source_memory_id, node->memory_id) != 0) {
        result = resolve_node(ctx, node->ultimate_source_memory_id);
        --ctx->visited_count;
        return result;
    }

    --ctx->visited_count;
    return result;
}

memoria_lineage_result memoria_lineage_resolve(
    const memoria_lineage_node *nodes,
    size_t node_count,
    const char *memory_id,
    const char *namespace_id
) {
    resolve_ctx ctx = {0};
    if (!nodes || !node_count || !memory_id || !*memory_id) return inactive_result();
    ctx.nodes = nodes;
    ctx.node_count = node_count;
    ctx.namespace_id = namespace_id ? namespace_id : "";
    return resolve_node(&ctx, memory_id);
}
