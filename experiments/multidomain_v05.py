from random import Random

from memoria_resolutiva.contextual import ContextAssociator
from memoria_resolutiva.evaluation import evaluate_hidden_pairs


PAIRS = [
    ("carro", "automovel"),
    ("guardar", "armazenar"),
    ("fibra", "enlace"),
    ("estrela", "astro"),
]

CONTEXTS = {
    ("carro", "automovel"): [
        ("eu", "dirijo", "{x}", "na", "estrada"),
        ("o", "{x}", "usa", "motor", "eletrico"),
        ("este", "{x}", "tem", "quatro", "rodas"),
    ],
    ("guardar", "armazenar"): [
        ("vou", "{x}", "dados", "no", "banco"),
        ("preciso", "{x}", "arquivo", "na", "memoria"),
        ("sistema", "deve", "{x}", "informacao", "local"),
    ],
    ("fibra", "enlace"): [
        ("sinal", "passa", "pela", "{x}", "optica"),
        ("perda", "no", "{x}", "foi", "medida"),
        ("olt", "monitora", "o", "{x}", "ativo"),
    ],
    ("estrela", "astro"): [
        ("luz", "da", "{x}", "chegou", "aqui"),
        ("massa", "do", "{x}", "foi", "estimada"),
        ("o", "{x}", "brilha", "no", "ceu"),
    ],
}

NOISE = ["ruido1", "ruido2", "ruido3", "rede", "galaxia", "memoria", "motor", "dados", "sinal", "tempo"]


def instantiate(template, target):
    return [target if token == "{x}" else token for token in template]


def build_corpus(exposures=20, noise_trajectories=500, seed=42):
    associator = ContextAssociator(radius=2)
    for pair, templates in CONTEXTS.items():
        for _ in range(exposures):
            for target in pair:
                for template in templates:
                    associator.observe(instantiate(template, target))

    rng = Random(seed)
    for _ in range(noise_trajectories):
        associator.observe(rng.sample(NOISE, 5))
    return associator


if __name__ == "__main__":
    model = build_corpus()
    metrics = evaluate_hidden_pairs(model, PAIRS, top_k=3)
    print(metrics)
    for a, b in PAIRS:
        print(f"{a:10s} <-> {b:10s}: {model.similarity(a, b):.4f}")
