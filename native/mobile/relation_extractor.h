#ifndef MEMORIA_RELATION_EXTRACTOR_H
#define MEMORIA_RELATION_EXTRACTOR_H

#include <stddef.h>

typedef struct memoria_relation {
    char subject[96];
    char predicate[32];
    char object[96];
    double confidence;
} memoria_relation;

/* Raw extractor remains observable for diagnostics and extractor regression tests. */
size_t memoria_extract_relations(const char *text, memoria_relation *out, size_t capacity);

/* Post-v1 promotion path: raw candidates are filtered by the semantic validator
 * before they are eligible for persistent graph materialization. */
size_t memoria_extract_promotable_relations(const char *text, memoria_relation *out, size_t capacity);

/* The post-v1 runtime sets provenance context around one ingest call. The
 * context is thread-local so concurrent native requests do not leak policy
 * into each other. assistant_generated remains storable/observable, but its
 * text is not eligible for automatic relation promotion. */
void memoria_relation_promotion_set_source_type(const char *source_type);
void memoria_relation_promotion_clear_source_type(void);

/* Only the post-v1 runtime source is compiled with this define. This redirects
 * its existing calls without editing the frozen v1 implementation included by it. */
#ifdef MEMORIA_RELATION_PROMOTION_FILTER
#define memoria_extract_relations memoria_extract_promotable_relations
#endif

#endif
