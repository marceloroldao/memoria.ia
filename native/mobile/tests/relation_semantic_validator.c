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
    memoria_relation input[5], output[5];
    size_t n;

    memoria_relation good = rel("sensor", "is", "active", 0.95);
    assert(memoria_relation_validate_for_promotion(&good, &v));
    assert(v.promotable == 1);
    assert(v.reason == MEMORIA_RELATION_VALID);

    memoria_relation numeric_subject = rel("7319", "is", "atlas", 0.95);
    assert(memoria_relation_validate_for_promotion(&numeric_subject, &v));
    assert(v.promotable == 0);
    assert(v.reason == MEMORIA_RELATION_NUMERIC_SUBJECT);

    memoria_relation numeric_identity = rel("atlas", "is", "7319", 0.95);
    assert(memoria_relation_validate_for_promotion(&numeric_identity, &v));
    assert(v.promotable == 0);
    assert(v.reason == MEMORIA_RELATION_NUMERIC_IDENTITY);

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
    n = memoria_relation_filter_promotable(input, 5, output, 5);
    assert(n == 3);
    assert(strcmp(output[0].subject, "sensor") == 0);
    assert(strcmp(output[1].subject, "temperature") == 0);
    assert(strcmp(output[2].subject, "battery") == 0);

    return 0;
}
