#ifndef MEMORIA_SEMANTIC_KERNEL_H
#define MEMORIA_SEMANTIC_KERNEL_H

#include <stddef.h>

typedef struct memoria_semantic_source {
    const char *memory_id;
    const char *text;
    double authority;
    long order;
} memoria_semantic_source;

typedef struct memoria_semantic_result {
    int hit; /* 1 HIT, 0 UNRESOLVED */
    const char *memory_id;
    double confidence;
} memoria_semantic_result;

memoria_semantic_result memoria_semantic_resolve_sources(
    const char *query,
    const memoria_semantic_source *sources,
    size_t source_count
);

#endif
