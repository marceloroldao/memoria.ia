#include "relation_extractor.h"
#include <assert.h>
#include <math.h>
#include <string.h>

static int near(double a, double b) {
    return fabs(a - b) < 1e-12;
}

int main(void) {
    memoria_relation rows[8];
    size_t n;

    /* Existing native English support remains intact. */
    n = memoria_extract_relations("server is atlas; laboratory is north", rows, 8);
    assert(n == 2);
    assert(strcmp(rows[0].subject, "server") == 0);
    assert(strcmp(rows[0].predicate, "is") == 0);
    assert(strcmp(rows[0].object, "atlas") == 0);
    assert(strcmp(rows[1].subject, "laboratory") == 0);
    assert(strcmp(rows[1].object, "north") == 0);

    n = memoria_extract_relations("sensor = active", rows, 8);
    assert(n == 1);
    assert(strcmp(rows[0].subject, "sensor") == 0);
    assert(strcmp(rows[0].object, "active") == 0);
    assert(near(rows[0].confidence, 0.95));

    /* Product-conversation prefixes are discarded from the relation term. */
    n = memoria_extract_relations("meu servidor é um atlas", rows, 8);
    assert(n == 1);
    assert(strcmp(rows[0].subject, "servidor") == 0);
    assert(strcmp(rows[0].object, "atlas") == 0);
    assert(near(rows[0].confidence, 0.95));

    n = memoria_extract_relations("Minha bateria = carregada", rows, 8);
    assert(n == 1);
    assert(strcmp(rows[0].subject, "bateria") == 0);
    assert(strcmp(rows[0].object, "carregada") == 0);

    /* Explicit copular rows are emitted before the lower-confidence elliptic row. */
    n = memoria_extract_relations("meu carro é um sedan e o motor um v8", rows, 8);
    assert(n == 2);
    assert(strcmp(rows[0].subject, "carro") == 0);
    assert(strcmp(rows[0].object, "sedan") == 0);
    assert(near(rows[0].confidence, 0.95));
    assert(strcmp(rows[1].subject, "motor") == 0);
    assert(strcmp(rows[1].object, "v8") == 0);
    assert(near(rows[1].confidence, 0.85));

    n = memoria_extract_relations("o alpha é um nodo; o beta um espelho", rows, 8);
    assert(n == 2);
    assert(strcmp(rows[0].subject, "alpha") == 0);
    assert(strcmp(rows[0].object, "nodo") == 0);
    assert(strcmp(rows[1].subject, "beta") == 0);
    assert(strcmp(rows[1].object, "espelho") == 0);

    /* Product semantics deduplicate equivalent repeated relations. */
    n = memoria_extract_relations("sensor = active; sensor = active", rows, 8);
    assert(n == 1);

    /* Relation-noise terms never become authoritative relation endpoints. */
    n = memoria_extract_relations("o outro é ativo", rows, 8);
    assert(n == 0);

    n = memoria_extract_relations("conversation without explicit relation", rows, 8);
    assert(n == 0);
    return 0;
}
