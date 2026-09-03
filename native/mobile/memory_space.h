#ifndef MEMORIA_MEMORY_SPACE_H
#define MEMORIA_MEMORY_SPACE_H

#include <string.h>

typedef enum memoria_memory_space {
    MEMORIA_MEMORY_SPACE_FACTUAL = 1,
    MEMORIA_MEMORY_SPACE_GENERATIVE = 2
} memoria_memory_space;

static inline memoria_memory_space memoria_memory_space_for_source_type(const char *source_type) {
    if (source_type && (
        strcmp(source_type, "assistant_generated") == 0 ||
        strcmp(source_type, "retrieved_replay") == 0
    )) return MEMORIA_MEMORY_SPACE_GENERATIVE;
    return MEMORIA_MEMORY_SPACE_FACTUAL;
}

static inline int memoria_may_be_factual_root(const char *source_type) {
    return memoria_memory_space_for_source_type(source_type) == MEMORIA_MEMORY_SPACE_FACTUAL;
}

#endif
