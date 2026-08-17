from memoria_resolutiva.emergent_ontology import EmergentOntology, cluster_purity


def main():
    ontology = EmergentOntology(radius=3, threshold=0.55)
    sentences = [
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
    ]
    ontology.observe_many(sentences)
    terms = ["tarifa", "cobranca", "encargo", "estrela", "astro"]
    labels = {
        "tarifa": "fee",
        "cobranca": "fee",
        "encargo": "fee",
        "estrela": "star",
        "astro": "star",
    }
    clusters = ontology.cluster(terms)
    print("clusters:", clusters)
    print("purity:", cluster_purity(clusters, labels))
    for a in terms:
        print(a, ontology.memory.nearest(a, top_k=4))


if __name__ == "__main__":
    main()
