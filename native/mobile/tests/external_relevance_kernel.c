#include "external_relevance_kernel.h"

#include <assert.h>

static memoria_external_relevance_policy policy(void) {
    memoria_external_relevance_policy p;
    p.min_query_coverage = 0.60;
    p.min_anchor_matches = 1u;
    p.early_window_tokens = 24u;
    return p;
}

int main(void) {
    memoria_external_relevance_result r;
    memoria_external_relevance_policy p = policy();

    assert(memoria_external_relevance_evaluate(
        "quais oceanos existem no planeta",
        "Os oceanos da Terra incluem Pacifico, Atlantico, Indico, Artico e Antartico.",
        &p, &r));
    assert(r.accepted == 1);
    assert(r.query_coverage >= 0.60);

    assert(memoria_external_relevance_evaluate(
        "informacoes sobre o pais china",
        "Air China anunciou novos voos e resultados financeiros da companhia aerea.",
        &p, &r));
    assert(r.accepted == 0);
    assert(r.query_coverage < 0.60);

    assert(memoria_external_relevance_evaluate(
        "informacoes sobre o pais china",
        "China e um pais do leste asiatico, com populacao e territorio extensos.",
        &p, &r));
    assert(r.accepted == 1);

    assert(memoria_external_relevance_evaluate(
        "qual é a capital do brasil",
        "Brasilia e a capital do Brasil e sede do governo federal.",
        &p, &r));
    assert(r.accepted == 1);

    assert(memoria_external_relevance_evaluate(
        "qual é a capital do brasil",
        "O campeonato brasileiro teve rodada com varios clubes e estadios.",
        &p, &r));
    assert(r.accepted == 0);

    /* Common Portuguese accents normalize deterministically. */
    assert(memoria_external_relevance_evaluate(
        "população do Brasil",
        "A populacao do brasil e estimada por levantamentos demograficos.",
        &p, &r));
    assert(r.accepted == 1);

    return 0;
}
