#ifndef MEMORIA_RELATION_EXTRACTOR_H
#define MEMORIA_RELATION_EXTRACTOR_H

#include <stddef.h>

typedef struct memoria_relation {
    char subject[96];
    char predicate[32];
    char object[96];
    double confidence;
} memoria_relation;

size_t memoria_extract_relations(const char *text, memoria_relation *out, size_t capacity);

#endif
