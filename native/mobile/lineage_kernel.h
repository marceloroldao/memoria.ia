#ifndef MEMORIA_LINEAGE_KERNEL_H
#define MEMORIA_LINEAGE_KERNEL_H

#include <stddef.h>

#define MEMORIA_LINEAGE_MAX_PARENTS 16u

typedef struct memoria_lineage_node {
    const char *memory_id;
    const char *namespace_id;
    const char *source_type;
    const char *ultimate_source_memory_id;
    const char *parent_memory_ids[MEMORIA_LINEAGE_MAX_PARENTS];
    size_t parent_count;
    double authority;
    long order;
    int superseded;
} memoria_lineage_node;

typedef struct memoria_lineage_result {
    int factual_active;
    const char *representative_root_id;
    size_t required_parent_count;
    size_t active_parent_count;
} memoria_lineage_result;

int memoria_lineage_is_factual_root_type(const char *source_type);
int memoria_lineage_is_conjunctive_type(const char *source_type);

memoria_lineage_result memoria_lineage_resolve(
    const memoria_lineage_node *nodes,
    size_t node_count,
    const char *memory_id,
    const char *namespace_id
);

#endif
