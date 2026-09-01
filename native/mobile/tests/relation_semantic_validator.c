#include "relation_semantic_validator.h"

#include <assert.h>
#include <string.h>

static memoria_relation rel(const char *s, const char *p, const char *o, double c) {
    memoria_relation r;
    memset(&r, 0, sizeof(r));
    strncpy(r.subject, s, sizeof(r.subject)-1);
    strncpy(r.predicate, p, sizeof(r.predicate)-1);
    strncpy(r.object, o, sizeof(r.object)-1);
    r.confidence = c;
    return r;
}

int main(void) {
    memoria_relation_validation_result v;
    memoria_relation input[7], output[7];
    size_t n;

    memoria_relation good = rel("sensor", "is", "active", 0.95);
    assert(memoria_relation_validate_for_promotion(&good, &v));
    assert(v.promotable == 1);
    assert(v.reason == MEMORIA_RELATION_VALID);

    memoria_relation numeric_subject = rel("7319", "is", "atlas", 0.95);
    assert(memoria_relation_validate_for_promotion(&numeric_subject, &v));
    assert(v.promotable == 0);
    assert(v.reason == MEMORIA_RELATION_NUMERIC_SUBJECT);

    /* Bare entity=number stays conservative. */
    memoria_relation numeric_identity = rel("atlas", "is", "7319", 0.95);
    assert(memoria_relation_validate_for_promotion(&numeric_identity, &v));
    assert(v.promotable == 0);
    assert(v.reason == MEMORIA_RELATION_NUMERIC_IDENTITY);

    /* Explicit numeric attributes must remain valid; consolidation/conflict relies on this shape. */
    memoria_relation code = rel("atlas code", "is", "7319", 0.95);
    assert(memoria_relation_validate_for_promotion(&code, &v));
    assert(v.promotable == 1);
    assert(v.reason == MEMORIA_RELATION_VALID);

    memoria_relation temperature = rel("temperature", "is", "25", 0.90);
    assert(memoria_relation_validate_for_promotion(&temperature, &v));
    assert(v.promotable == 1);

    memoria_relation self = rel("brasil", "is", "Brasil", 0.95);
    assert(memoria_relation_validate_for_promotion(&self, &v));
    assert(v.promotable == 0);
    assert(v.reason == MEMORIA_RELATION_SELF_IDENTITY);

    memoria_relation low = rel("sensor", "is", "active", 0.30);
    assert(memoria_relation_validate_for_promotion(&low, &v));
    assert(v.promotable == 0);
    assert(v.reason == MEMORIA_RELATION_LOW_CONFIDENCE);

    memoria_relation url = rel("https://example.com/a", "is", "active", 0.95);
    assert(memoria_relation_validate_for_promotion(&url, &v));
    assert(v.promotable == 0);
    assert(v.reason == MEMORIA_RELATION_URL_LIKE);

    input[0] = good;
    input[1] = numeric_subject;
    input[2] = rel("temperature", "is", "high", 0.85);
    input[3] = self;
    input[4] = rel("battery", "is", "charged", 0.90);
    input[5] = code;
    input[6] = numeric_identity;
    n = memoria_relation_filter_promotable(input, 7, output, 7);
    assert(n == 4);
    assert(strcmp(output[0].subject, "sensor") == 0);
    assert(strcmp(output[1].subject, "temperature") == 0);
    assert(strcmp(output[2].subject, "battery") == 0);
    assert(strcmp(output[3].subject, "atlas code") == 0);

    return 0;
}
