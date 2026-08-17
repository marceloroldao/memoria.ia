from memoria_resolutiva.contextual import ContextAssociator


def main() -> None:
    model = ContextAssociator(radius=2)
    corpus = [
        ["inicio", "carro", "percorre", "estrada", "fim"],
        ["inicio", "automovel", "percorre", "estrada", "fim"],
        ["inicio", "carro", "segue", "rodovia", "fim"],
        ["inicio", "automovel", "segue", "rodovia", "fim"],
        ["inicio", "estrela", "brilha", "ceu", "fim"],
        ["inicio", "galaxia", "gira", "cosmos", "fim"],
    ]
    for trajectory in corpus:
        model.observe(trajectory)

    print("carro ~ automovel:", round(model.similarity("carro", "automovel"), 4))
    print("carro ~ estrela   :", round(model.similarity("carro", "estrela"), 4))
    print("nearest(carro)    :", model.nearest("carro", top_k=4))


if __name__ == "__main__":
    main()
