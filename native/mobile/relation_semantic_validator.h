#ifndef MEMORIA_RELATION_SEMANTIC_VALIDATOR_H
#define MEMORIA_RELATION_SEMANTIC_VALIDATOR_H

#include <stddef.h>
#include "relation_extractor.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef enum memoria_relation_validation_reason {
    MEMORIA_RELATION_VALID = 0,
    MEMORIA_RELATION_EMPTY_FIELD = 1,
    MEMORIA_RELATION_NUMERIC_SUBJECT = 2,
    MEMORIA_RELATION_NUMERIC_IDENTITY = 3,
    MEMORIA_RELATION_SELF_IDENTITY = 4,
    MEMORIA_RELATION_NOISE_TOKEN = 5,
    MEMORIA_RELATION_URL_LIKE = 6,
    MEMORIA_RELATION_LOW_CONFIDENCE = 7
} memoria_relation_validation_reason;

typedef struct memoria_relation_validation_result {
    int promotable;
    memoria_relation_validation_reason reason;
    double semantic_confidence;
} memoria_relation_validation_result;

int memoria_relation_validate_for_promotion(
    const memoria_relation *relation,
    memoria_relation_validation_result *out
);

size_t memoria_relation_filter_promotable(
    const memoria_relation *input,
    size_t input_count,
    memoria_relation *output,
    size_t output_capacity
);

const char *memoria_relation_validation_reason_name(memoria_relation_validation_reason reason);

#ifdef __cplusplus
}
#endif
#endif
