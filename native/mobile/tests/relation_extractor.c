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

    n = memoria_extract_relations("meu servidor é um atlas", rows, 8);
    assert(n == 1);
    assert(strcmp(rows[0].subject, "servidor") == 0);
    assert(strcmp(rows[0].object, "atlas") == 0);
    assert(near(rows[0].confidence, 0.95));

    n = memoria_extract_relations("Minha bateria = carregada", rows, 8);
    assert(n == 1);
    assert(strcmp(rows[0].subject, "bateria") == 0);
    assert(strcmp(rows[0].object, "carregada") == 0);

    /* Naming creates an instance/member relation: named entity -> type. */
    n = memoria_extract_relations("meu gato se chama Lotus", rows, 8);
    assert(n == 1);
    assert(strcmp(rows[0].subject, "Lotus") == 0);
    assert(strcmp(rows[0].predicate, "is") == 0);
    assert(strcmp(rows[0].object, "gato") == 0);
    assert(near(rows[0].confidence, 0.95));

    n = memoria_extract_relations("sensor se chama Atlas", rows, 8);
    assert(n == 1);
    assert(strcmp(rows[0].subject, "Atlas") == 0);
    assert(strcmp(rows[0].object, "sensor") == 0);

    n = memoria_extract_relations("gato chamado Alt", rows, 8);
    assert(n == 1);
    assert(strcmp(rows[0].subject, "Alt") == 0);
    assert(strcmp(rows[0].object, "gato") == 0);

    n = memoria_extract_relations("node named Orion", rows, 8);
    assert(n == 1);
    assert(strcmp(rows[0].subject, "Orion") == 0);
    assert(strcmp(rows[0].object, "node") == 0);

    n = memoria_extract_relations("eu tenho um gato que se chama lotus", rows, 8);
    assert(n == 1);
    assert(strcmp(rows[0].subject, "lotus") == 0);
    assert(strcmp(rows[0].predicate, "is") == 0);
    assert(strcmp(rows[0].object, "gato") == 0);

    n = memoria_extract_relations("ele tem um irmão, que se chama  Vibe", rows, 8);
    assert(n == 1);
    assert(strcmp(rows[0].subject, "Vibe") == 0);
    assert(strcmp(rows[0].predicate, "is") == 0);
    assert(strcmp(rows[0].object, "irmão") == 0);

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

    n = memoria_extract_relations("sensor = active; sensor = active", rows, 8);
    assert(n == 1);

    n = memoria_extract_relations("o outro é ativo", rows, 8);
    assert(n == 0);

    n = memoria_extract_relations("isso é verdade", rows, 8); assert(n == 0);
    n = memoria_extract_relations("isto é importante", rows, 8); assert(n == 0);
    n = memoria_extract_relations("aquilo é estranho", rows, 8); assert(n == 0);
    n = memoria_extract_relations("ele é azul", rows, 8); assert(n == 0);
    n = memoria_extract_relations("ela é engenheira", rows, 8); assert(n == 0);
    n = memoria_extract_relations("aqui é frio", rows, 8); assert(n == 0);

    n = memoria_extract_relations("quem é atlas", rows, 8); assert(n == 0);
    n = memoria_extract_relations("onde é norte", rows, 8); assert(n == 0);
    n = memoria_extract_relations("como é azul", rows, 8); assert(n == 0);

    n = memoria_extract_relations("conversation without explicit relation", rows, 8);
    assert(n == 0);
    return 0;
}
