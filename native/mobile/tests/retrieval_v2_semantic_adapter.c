#include "retrieval_v2_semantic_adapter.h"
#include "semantic_kernel.h"

#include <assert.h>
#include <string.h>

int main(void) {
    memoria_semantic_result baseline, v2;

    memoria_semantic_source electrical[] = {
        {"supply", "a tensão nominal do módulo principal é 24 volts", 1.0, 1, "user_assertion", "supply"},
        {"battery", "a bateria auxiliar possui capacidade de 80 ampere hora", 1.0, 2, "user_assertion", "battery"}
    };
    baseline = memoria_semantic_resolve_sources("qual a voltagem dos módulos principais", electrical, 2);
    v2 = memoria_retrieval_v2_resolve_sources("qual a voltagem dos módulos principais", electrical, 2);
    assert(baseline.hit == 0);
    assert(v2.hit == 1);
    assert(strcmp(v2.memory_id, "supply") == 0);

    memoria_semantic_source infrastructure[] = {
        {"server", "o servidor de borda usa a porta 8443", 1.0, 1, "user_assertion", "server"},
        {"sensor", "o sensor de temperatura usa a porta 9000", 1.0, 2, "user_assertion", "sensor"}
    };
    baseline = memoria_semantic_resolve_sources("portas dos servidores de borda", infrastructure, 2);
    v2 = memoria_retrieval_v2_resolve_sources("portas dos servidores de borda", infrastructure, 2);
    assert(v2.hit == 1);
    assert(strcmp(v2.memory_id, "server") == 0);
    assert(!baseline.hit || strcmp(baseline.memory_id, "server") == 0);

    /* Existing entity-profile discrimination must survive normalization. */
    memoria_semantic_source china[] = {
        {"country", "República Popular da China é um país da Ásia Oriental com capital em Pequim.", 0.85, 1, "external_import", "country"},
        {"airline", "Air China é uma empresa aérea estatal da China com sede em Pequim.", 0.85, 2, "external_import", "airline"}
    };
    v2 = memoria_retrieval_v2_resolve_sources("me fale sobre a China", china, 2);
    assert(v2.hit == 1);
    assert(strcmp(v2.memory_id, "country") == 0);

    /* Authority remains independent from lexical normalization. */
    memoria_semantic_source generated[] = {
        {"direct", "a frequência do beacon é 433 megahertz", 1.0, 1, "user_assertion", "direct"},
        {"echo", "as frequências dos beacons são 999 megahertz", 0.25, 2, "assistant_generated", "echo"}
    };
    v2 = memoria_retrieval_v2_resolve_sources("frequencias dos beacons", generated, 2);
    assert(v2.hit == 1);
    assert(strcmp(v2.memory_id, "direct") == 0);

    /* Question-shaped stored turns remain non-retrievable after transient normalization. */
    memoria_semantic_source questions[] = {
        {"fact", "a capacidade da bateria é 80 unidades", 1.0, 1, "user_assertion", "fact"},
        {"question", "qual é a capacidade das baterias?", 1.0, 2, "user_assertion", "question"}
    };
    v2 = memoria_retrieval_v2_resolve_sources("capacidade das baterias", questions, 2);
    assert(v2.hit == 1);
    assert(strcmp(v2.memory_id, "fact") == 0);

    return 0;
}
