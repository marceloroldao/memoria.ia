#ifndef MEMORIA_TYPED_RELATION_EXTRACTOR_H
#define MEMORIA_TYPED_RELATION_EXTRACTOR_H

#include "relation_extractor.h"
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Extract only explicit ontology-typed relations. This is intentionally
 * conservative: generic copulas (`is`, `é`) are not converted into typed
 * predicates. Returned predicates currently include `esta_em`, `parte_de`
 * and `subclasse_de`. */
size_t memoria_extract_typed_relations(
    const char *text,
    memoria_relation *out,
    size_t capacity
);

#ifdef __cplusplus
}
#endif

#endif
