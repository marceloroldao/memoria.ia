from memoria_resolutiva.semantic_router_v96 import SemanticRouterV96


def main():
    r = SemanticRouterV96(threshold=0.55, min_margin=0.05)
    r.observe([
        "a tarifa mensal foi aplicada ao servico de fibra",
        "a cobranca mensal foi aplicada ao servico de fibra",
        "o encargo mensal foi aplicado ao servico de fibra",
        "a taxa mensal foi aplicada ao servico de fibra",
        "a estrela brilhante apareceu no ceu noturno",
        "o astro brilhante apareceu no ceu noturno",
        "a estrela distante foi observada pelo telescopio",
        "o astro distante foi observado pelo telescopio",
    ])
    r.register_concept("fee", ["tarifa"])
    r.register_concept("star", ["estrela"])

    fallback_calls = []

    def neural_fallback(query):
        fallback_calls.append(query)
        return "neural-result"

    queries = [
        "cobranca", "encargo", "taxa", "astro",
        "tarifa", "estrela", "desconhecido", "motor",
    ]
    results = [r.resolve_or_fallback(q, neural_fallback) for q in queries]
    metrics = r.metrics()

    print({
        "queries": len(queries),
        "memory_resolved": metrics.memory_resolved,
        "fallback_calls": metrics.fallback_calls,
        "deflection_rate": metrics.deflection_rate,
        "fallback_queries": fallback_calls,
        "results": [(x.query, x.concept_id, x.source, round(x.score, 4), round(x.margin, 4)) for x in results],
    })


if __name__ == "__main__":
    main()
