from memoria_resolutiva.contextual import ContextAssociator
from memoria_resolutiva.generalization import evaluate_pairs

PAIRS = [
    ("carro", "automovel"),
    ("guardar", "armazenar"),
    ("fibra", "enlace"),
    ("estrela", "astro"),
]

FAMILIES = {
    ("carro", "automovel"): [
        ("motor", "{x}", "rodovia"),
        ("garagem", "{x}", "volante"),
        ("combustivel", "{x}", "viagem"),
        ("pneu", "{x}", "transito"),
    ],
    ("guardar", "armazenar"): [
        ("arquivo", "{x}", "dados"),
        ("memoria", "{x}", "conteudo"),
        ("disco", "{x}", "backup"),
        ("registro", "{x}", "persistencia"),
    ],
    ("fibra", "enlace"): [
        ("olt", "{x}", "onu"),
        ("sinal", "{x}", "optico"),
        ("rede", "{x}", "potencia"),
        ("laser", "{x}", "conexao"),
    ],
    ("estrela", "astro"): [
        ("ceu", "{x}", "luz"),
        ("galaxia", "{x}", "espaco"),
        ("telescopio", "{x}", "brilho"),
        ("cosmos", "{x}", "observacao"),
    ],
}

DISTRACTOR_TRAJECTORIES = [
    ["motor", "veiculo", "cidade"],
    ["garagem", "veiculo", "rua"],
    ["arquivo", "salvar", "documento"],
    ["memoria", "salvar", "estado"],
    ["rede", "cabo", "potencia"],
    ["sinal", "cabo", "eletrico"],
    ["ceu", "planeta", "orbita"],
    ["telescopio", "planeta", "observacao"],
]

DISTRACTORS = {
    "carro": ["veiculo"], "automovel": ["veiculo"],
    "guardar": ["salvar"], "armazenar": ["salvar"],
    "fibra": ["cabo"], "enlace": ["cabo"],
    "estrela": ["planeta"], "astro": ["planeta"],
}


def build_model(noise: int = 1000) -> ContextAssociator:
    model = ContextAssociator(radius=2)
    for pair, templates in FAMILIES.items():
        for term in pair:
            for left, middle, right in templates:
                model.observe([left, middle.format(x=term), right])
    for trajectory in DISTRACTOR_TRAJECTORIES:
        model.observe(trajectory)
    for i in range(noise):
        model.observe([f"n{i % 31}", f"x{i % 101}", f"q{i % 37}"])
    return model


if __name__ == "__main__":
    model = build_model()
    metrics = evaluate_pairs(model, PAIRS, DISTRACTORS)
    print(metrics)
    for query, expected in PAIRS:
        print(query, "->", model.nearest(query, top_k=3), "expected:", expected)
