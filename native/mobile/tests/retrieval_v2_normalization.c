#include "retrieval_v2_normalization.h"

#include <assert.h>
#include <string.h>

static void expect(const char *input, const char *expected) {
    char out[96];
    assert(memoria_retrieval_v2_normalize_token(input, out, sizeof(out)) == 1);
    assert(strcmp(out, expected) == 0);
}

int main(void) {
    expect("tensão", "tensao");
    expect("tensões", "tensao");
    expect("voltagem", "tensao");
    expect("voltagens", "tensao");
    expect("frequências", "frequencia");
    expect("capacidades", "capacidade");
    expect("servidores", "servidor");
    expect("baterias", "bateria");
    expect("módulos", "modulo");
    expect("portas", "porta");
    expect("país", "pais");
    expect("países", "pais");
    expect("mais", "mais");
    expect("inglês", "ingles");
    expect("China", "china");
    return 0;
}
