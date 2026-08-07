from memoria_resolutiva.contextual import ContextAssociator


def test_contextual_association_emerges_without_declared_synonyms():
    model = ContextAssociator(radius=2)
    trajectories = [
        ["inicio", "carro", "percorre", "estrada", "fim"],
        ["inicio", "automovel", "percorre", "estrada", "fim"],
        ["inicio", "carro", "segue", "rodovia", "fim"],
        ["inicio", "automovel", "segue", "rodovia", "fim"],
        ["inicio", "estrela", "brilha", "ceu", "fim"],
        ["inicio", "galaxia", "gira", "cosmos", "fim"],
    ]
    for trajectory in trajectories:
        model.observe(trajectory)

    vehicle_similarity = model.similarity("carro", "automovel")
    unrelated_similarity = model.similarity("carro", "estrela")

    assert vehicle_similarity > 0.95
    assert unrelated_similarity < 0.50
    assert vehicle_similarity > unrelated_similarity


def test_nearest_context_returns_structurally_equivalent_node_first():
    model = ContextAssociator(radius=2)
    for trajectory in (
        ["start", "fibra", "mede", "sinal", "end"],
        ["start", "enlace", "mede", "sinal", "end"],
        ["start", "fibra", "transporta", "dados", "end"],
        ["start", "enlace", "transporta", "dados", "end"],
        ["start", "estrela", "emite", "luz", "end"],
    ):
        model.observe(trajectory)

    nearest = model.nearest("fibra", top_k=2)
    assert nearest
    assert nearest[0][0] == "enlace"
    assert nearest[0][1] > nearest[1][1]
