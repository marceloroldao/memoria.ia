from memoria_resolutiva.textual import TextContextMemory

TRAIN = [
    "o carro percorreu a estrada durante a viagem",
    "o motorista estacionou o carro perto da garagem",
    "o carro recebeu manutencao antes de seguir viagem",
    "o automovel percorreu a estrada durante a viagem",
    "o motorista estacionou o automovel perto da garagem",
    "o automovel recebeu manutencao antes de seguir viagem",
    "o sistema deve guardar os dados antes de desligar",
    "vamos guardar o arquivo para recuperar depois",
    "o banco consegue guardar informacao de forma persistente",
    "o sistema deve armazenar os dados antes de desligar",
    "vamos armazenar o arquivo para recuperar depois",
    "o banco consegue armazenar informacao de forma persistente",
    "a fibra transporta sinal optico entre os equipamentos",
    "o tecnico mediu potencia na fibra durante o teste",
    "a fibra conecta a rede ao equipamento remoto",
    "o enlace transporta sinal optico entre os equipamentos",
    "o tecnico mediu potencia no enlace durante o teste",
    "o enlace conecta a rede ao equipamento remoto",
    "a estrela emite luz observada pelo telescopio",
    "a estrela possui temperatura elevada e grande massa",
    "o telescopio registrou a estrela durante a noite",
    "o astro emite luz observada pelo telescopio",
    "o astro possui temperatura elevada e grande massa",
    "o telescopio registrou o astro durante a noite",
    # Ambiguity: banco appears in financial and storage contexts.
    "o banco aprovou credito para a empresa",
    "o banco recebeu deposito durante a manha",
    "o banco de dados manteve registros persistentes",
    "o banco de dados recuperou informacoes antigas",
]

PAIRS = [
    ("carro", "automovel"),
    ("guardar", "armazenar"),
    ("fibra", "enlace"),
    ("estrela", "astro"),
]


def main():
    memory = TextContextMemory(radius=3)
    memory.observe_many(TRAIN)

    correct = 0
    margins = []
    candidates = {x for pair in PAIRS for x in pair}
    for a, b in PAIRS:
        for query, target in ((a, b), (b, a)):
            ranked = sorted(
                ((c, memory.associator.similarity(query, c)) for c in candidates if c != query),
                key=lambda item: item[1],
                reverse=True,
            )
            hit = bool(ranked and ranked[0][0] == target)
            correct += int(hit)
            margin = ranked[0][1] - (ranked[1][1] if len(ranked) > 1 else 0.0)
            margins.append(margin)
            print(query, "->", ranked[:3], "hit=", hit, "margin=", round(margin, 4))

    probe = memory.ambiguity_probe("banco", top_k=5)
    print("\nTop-1:", f"{correct}/{len(PAIRS)*2}")
    print("Mean margin:", round(sum(margins) / len(margins), 4))
    print("Banco ambiguity entropy:", round(probe.normalized_entropy, 4))
    print("Banco margin:", round(probe.margin, 4))
    print("Banco alternatives:", probe.alternatives)


if __name__ == "__main__":
    main()
