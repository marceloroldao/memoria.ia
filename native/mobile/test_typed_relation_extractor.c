#include "typed_relation_extractor.h"

#include <assert.h>
#include <string.h>

static void expect_one(const char *text, const char *s, const char *p, const char *o) {
    memoria_relation r[2];
    size_t n = memoria_extract_typed_relations(text, r, 2);
    assert(n == 1);
    assert(strcmp(r[0].subject, s) == 0);
    assert(strcmp(r[0].predicate, p) == 0);
    assert(strcmp(r[0].object, o) == 0);
}

int main(void) {
    memoria_relation r[4];

    expect_one("Porto Alegre está em Rio Grande do Sul.", "Porto Alegre", "esta_em", "Rio Grande do Sul");
    expect_one("Rio Grande do Sul esta em Brasil", "Rio Grande do Sul", "esta_em", "Brasil");
    expect_one("motor faz parte de veículo", "motor", "parte_de", "veículo");
    expect_one("gato é subclasse de mamífero", "gato", "subclasse_de", "mamífero");
    expect_one("wheel is part of vehicle", "wheel", "parte_de", "vehicle");

    /* Generic copulas remain deliberately untyped. */
    assert(memoria_extract_typed_relations("atlas is servidor", r, 4) == 0);
    assert(memoria_extract_typed_relations("atlas é servidor", r, 4) == 0);

    /* Non-transitive relations are not invented from surface language. */
    assert(memoria_extract_typed_relations("Alt é irmão de Alt2", r, 4) == 0);
    assert(memoria_extract_typed_relations("Alt2 tem cor preta", r, 4) == 0);
    assert(memoria_extract_typed_relations("servidor usa porta 443", r, 4) == 0);
    return 0;
}
