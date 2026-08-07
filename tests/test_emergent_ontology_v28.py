from memoria_resolutiva.emergent_ontology import EmergentOntology, cluster_purity


def build():
    o = EmergentOntology(radius=3, threshold=0.55)
    o.observe_many([
        "a tarifa mensal foi aplicada ao servico de fibra",
        "a cobranca mensal foi aplicada ao servico de fibra",
        "o encargo mensal foi aplicado ao servico de fibra",
        "a tarifa adicional afetou o provedor de internet",
        "a cobranca adicional afetou o provedor de internet",
        "o encargo adicional afetou o provedor de internet",
        "a estrela brilhante apareceu no ceu noturno",
        "o astro brilhante apareceu no ceu noturno",
        "a estrela distante foi observada pelo telescopio",
        "o astro distante foi observado pelo telescopio",
    ])
    return o


def test_fee_terms_cluster_without_manual_synonym_map():
    o = build()
    clusters = o.cluster(["tarifa", "cobranca", "encargo"])
    assert any(set(c) == {"tarifa", "cobranca", "encargo"} for c in clusters)


def test_unrelated_domains_remain_separate():
    o = build()
    clusters = o.cluster(["tarifa", "cobranca", "encargo", "estrela", "astro"])
    labels = {"tarifa":"fee","cobranca":"fee","encargo":"fee","estrela":"star","astro":"star"}
    assert cluster_purity(clusters, labels) >= 0.8


def test_new_term_can_join_existing_cluster_online():
    o = build()
    before = o.cluster(["tarifa", "cobranca", "encargo", "taxa"])
    assert not any("taxa" in c and len(c) > 1 for c in before)
    o.observe_many([
        "a taxa mensal foi aplicada ao servico de fibra",
        "a taxa adicional afetou o provedor de internet",
    ])
    after = o.cluster(["tarifa", "cobranca", "encargo", "taxa"])
    assert any(set(c) == {"tarifa", "cobranca", "encargo", "taxa"} for c in after)
