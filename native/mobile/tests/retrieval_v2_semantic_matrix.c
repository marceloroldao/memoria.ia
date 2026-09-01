#include "retrieval_v2_semantic_adapter.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static void expect_hit(const char *query, memoria_semantic_source *sources, size_t n, const char *id) {
    memoria_semantic_result r = memoria_retrieval_v2_resolve_sources(query, sources, n);
    if (!(r.hit == 1 && r.memory_id && strcmp(r.memory_id, id) == 0)) {
        fprintf(stderr, "expected HIT %s for query: %s; got hit=%d id=%s\n", id, query, r.hit, r.memory_id ? r.memory_id : "<null>");
        assert(0);
    }
}

static void expect_miss(const char *query, memoria_semantic_source *sources, size_t n) {
    memoria_semantic_result r = memoria_retrieval_v2_resolve_sources(query, sources, n);
    if (r.hit != 0) {
        fprintf(stderr, "expected MISS for query: %s; got id=%s confidence=%.6f\n", query, r.memory_id ? r.memory_id : "<null>", r.confidence);
        assert(0);
    }
}

int main(void) {
    memoria_semantic_source electrical[] = {
        {"v24", "A tensão nominal do módulo principal é 24 volts.", 1.0, 1, "user_assertion", "v24"},
        {"freq", "A frequência do módulo principal é 50 hertz.", 1.0, 2, "user_assertion", "freq"},
        {"battery", "As baterias auxiliares possuem capacidade de 100 ampere-hora.", 1.0, 3, "user_assertion", "battery"}
    };
    expect_hit("qual a voltagem dos módulos principais", electrical, 3, "v24");
    expect_hit("frequencias do modulo principal", electrical, 3, "freq");
    expect_hit("capacidade da bateria auxiliar", electrical, 3, "battery");

    memoria_semantic_source infra[] = {
        {"srv", "O servidor de autenticação utiliza a porta 1812.", 1.0, 1, "user_assertion", "srv"},
        {"switch", "O switch de borda utiliza a porta 22 para administração.", 1.0, 2, "user_assertion", "switch"}
    };
    expect_hit("portas do servidor de autenticacao", infra, 2, "srv");

    memoria_semantic_source china[] = {
        {"country", "A China é um país da Ásia Oriental com capital em Pequim.", 0.85, 1, "external_import", "country"},
        {"airline", "Air China é uma empresa aérea estatal com voos internacionais.", 0.85, 2, "external_import", "airline"}
    };
    expect_hit("me fale sobre a China", china, 2, "country");

    memoria_semantic_source authority[] = {
        {"direct", "A tensão do barramento é 48 volts.", 1.0, 1, "user_assertion", "direct"},
        {"generated", "A voltagem do barramento é 96 volts.", 0.35, 2, "assistant_generated", "q"}
    };
    expect_hit("voltagem do barramento", authority, 2, "direct");

    memoria_semantic_source questions[] = {
        {"q", "qual a tensão do módulo?", 1.0, 1, "user_assertion", "q"},
        {"fact", "A tensão do módulo é 12 volts.", 1.0, 2, "user_assertion", "fact"}
    };
    expect_hit("voltagem do modulo", questions, 2, "fact");

    memoria_semantic_source ambiguous[] = {
        {"a", "O servidor norte usa a porta 443.", 1.0, 1, "user_assertion", "a"},
        {"b", "O servidor sul usa a porta 8443.", 1.0, 2, "user_assertion", "b"}
    };
    expect_miss("porta do servidor", ambiguous, 2);

    memoria_semantic_source protected_words[] = {
        {"br", "O Brasil é um país da América do Sul.", 0.85, 1, "external_import", "br"},
        {"en", "O idioma inglês é usado neste manual.", 0.85, 2, "external_import", "en"}
    };
    expect_hit("pais brasil", protected_words, 2, "br");
    expect_hit("idioma ingles", protected_words, 2, "en");

    expect_miss("frequencia do satelite desconhecido", electrical, 3);
    return 0;
}
