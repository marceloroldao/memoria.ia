#include "relation_semantic_validator.h"

#include <ctype.h>
#include <string.h>

static int ci_equal(const char *a, const char *b) {
    unsigned char ca, cb;
    if (!a || !b) return a == b;
    while (*a && *b) {
        ca = (unsigned char)*a++;
        cb = (unsigned char)*b++;
        if (ca < 0x80u) ca = (unsigned char)tolower(ca);
        if (cb < 0x80u) cb = (unsigned char)tolower(cb);
        if (ca != cb) return 0;
    }
    return *a == 0 && *b == 0;
}

static int numeric_only(const char *s) {
    int have_digit = 0;
    if (!s || !*s) return 0;
    for (; *s; ++s) {
        unsigned char c = (unsigned char)*s;
        if (isdigit(c)) { have_digit = 1; continue; }
        if (c == '.' || c == ',' || c == '-' || c == '+' || c == '%' || isspace(c)) continue;
        return 0;
    }
    return have_digit;
}

static int url_like(const char *s) {
    return s && (strstr(s, "://") != NULL || strstr(s, "www.") != NULL || strstr(s, ".com/") != NULL);
}

static int noise(const char *s) {
    static const char *terms[] = {
        "a","o","as","os","um","uma","de","do","da","dos","das","e","em","no","na","nos","nas",
        "eu","me","meu","minha","que","qual","quais","voce","você","isso","isto","aquilo","the","an","of","to"
    };
    size_t i;
    if (!s || !*s) return 1;
    for (i = 0; i < sizeof(terms)/sizeof(terms[0]); ++i) if (ci_equal(s, terms[i])) return 1;
    return 0;
}

const char *memoria_relation_validation_reason_name(memoria_relation_validation_reason reason) {
    switch (reason) {
        case MEMORIA_RELATION_VALID: return "valid";
        case MEMORIA_RELATION_EMPTY_FIELD: return "empty_field";
        case MEMORIA_RELATION_NUMERIC_SUBJECT: return "numeric_subject";
        case MEMORIA_RELATION_NUMERIC_IDENTITY: return "numeric_identity";
        case MEMORIA_RELATION_SELF_IDENTITY: return "self_identity";
        case MEMORIA_RELATION_NOISE_TOKEN: return "noise_token";
        case MEMORIA_RELATION_URL_LIKE: return "url_like";
        case MEMORIA_RELATION_LOW_CONFIDENCE: return "low_confidence";
        default: return "unknown";
    }
}

int memoria_relation_validate_for_promotion(
    const memoria_relation *relation,
    memoria_relation_validation_result *out
) {
    memoria_relation_validation_reason reason = MEMORIA_RELATION_VALID;
    double semantic_confidence;
    if (!relation || !out) return 0;

    if (!relation->subject[0] || !relation->predicate[0] || !relation->object[0])
        reason = MEMORIA_RELATION_EMPTY_FIELD;
    else if (relation->confidence < 0.50)
        reason = MEMORIA_RELATION_LOW_CONFIDENCE;
    else if (url_like(relation->subject) || url_like(relation->object))
        reason = MEMORIA_RELATION_URL_LIKE;
    else if (noise(relation->subject) || noise(relation->object))
        reason = MEMORIA_RELATION_NOISE_TOKEN;
    else if (ci_equal(relation->subject, relation->object))
        reason = MEMORIA_RELATION_SELF_IDENTITY;
    else if (numeric_only(relation->subject))
        reason = MEMORIA_RELATION_NUMERIC_SUBJECT;
    else if (ci_equal(relation->predicate, "is") && numeric_only(relation->object))
        reason = MEMORIA_RELATION_NUMERIC_IDENTITY;

    semantic_confidence = relation->confidence;
    if (reason != MEMORIA_RELATION_VALID) semantic_confidence = 0.0;

    out->promotable = reason == MEMORIA_RELATION_VALID;
    out->reason = reason;
    out->semantic_confidence = semantic_confidence;
    return 1;
}

size_t memoria_relation_filter_promotable(
    const memoria_relation *input,
    size_t input_count,
    memoria_relation *output,
    size_t output_capacity
) {
    size_t i, count = 0u;
    memoria_relation_validation_result result;
    if ((!input && input_count) || !output || output_capacity == 0u) return 0u;
    for (i = 0; i < input_count && count < output_capacity; ++i) {
        if (memoria_relation_validate_for_promotion(&input[i], &result) && result.promotable)
            output[count++] = input[i];
    }
    return count;
}
