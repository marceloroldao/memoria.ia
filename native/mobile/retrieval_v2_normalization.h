#ifndef MEMORIA_RETRIEVAL_V2_NORMALIZATION_H
#define MEMORIA_RETRIEVAL_V2_NORMALIZATION_H

#include <stddef.h>

/* Deterministic, non-neural lexical normalization for Retrieval v2.
 * Returns 1 when a non-empty canonical token was produced, otherwise 0.
 * The output is lowercase ASCII where supported by the conservative UTF-8 fold.
 */
int memoria_retrieval_v2_normalize_token(const char *input, char *out, size_t out_size);

#endif
